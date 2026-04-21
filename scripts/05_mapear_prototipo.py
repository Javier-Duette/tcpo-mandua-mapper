"""05_mapear_prototipo.py - Matching TCPO->Mandua con estrategia D-003."""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import get_connection
from src.gemini_client import init_gemini
from src.matching import (
    decidir_tabla_destino,
    es_composicion_auxiliar,
    match_embedding,
    match_exacto,
    match_fuzzy,
    normalizar,
    TABLA_A_TIPO,
)
from src.embeddings import cargar_embeddings_mandua

FUZZY_UMBRAL = 75
EMBED_UMBRAL = 0.70


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_candidates(conn, tabla: str) -> list[dict]:
    """Devuelve lista de dicts con id y descripcion_normalizada para matching."""
    if tabla in ("mandua_materiales", "mandua_mano_obra"):
        rows = conn.execute(
            f"SELECT id, descripcion_normalizada FROM {tabla}"
        ).fetchall()
        return [{"id": r["id"], "descripcion_normalizada": r["descripcion_normalizada"]} for r in rows]
    if tabla == "mandua_costeo":
        rows = conn.execute("SELECT id, partida FROM mandua_costeo").fetchall()
        return [
            {"id": r["id"], "descripcion_normalizada": normalizar(r["partida"] or "")}
            for r in rows
        ]
    return []


def _col(s, w):
    s = str(s) if s is not None else ""
    return (s[:w - 1] + ">") if len(s) >= w else s.ljust(w)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    conn = get_connection()

    # --- Pre-flight ---
    n_traducidos = conn.execute(
        "SELECT COUNT(*) FROM tcpo_items WHERE descripcion_es IS NOT NULL"
    ).fetchone()[0]
    print(f"Items con descripcion_es: {n_traducidos}")
    if n_traducidos != 30:
        print(f"  WARNING: se esperaban 30, se encontraron {n_traducidos}")
        if n_traducidos == 0:
            print("  ERROR: no hay items traducidos. Correr 04_traducir_prototipo.py primero.")
            sys.exit(1)

    # --- Cargar items TCPO traducidos ---
    tcpo_rows = conn.execute(
        "SELECT id, codigo, class, descripcion_pt, descripcion_es, subcapitulo, fila_original "
        "FROM tcpo_items WHERE descripcion_es IS NOT NULL"
    ).fetchall()

    # --- Cargar candidatos Mandua para cada tabla ---
    print("\nCargando candidatos Mandua...")
    candidatos = {
        "mandua_materiales": _build_candidates(conn, "mandua_materiales"),
        "mandua_mano_obra":   _build_candidates(conn, "mandua_mano_obra"),
        "mandua_costeo":      _build_candidates(conn, "mandua_costeo"),
    }
    for t, c in candidatos.items():
        print(f"  {t}: {len(c)} candidatos")

    # --- Inicializar Gemini y cargar embeddings ---
    print("\nInicializando Gemini...")
    client = init_gemini()

    print("\nCargando embeddings Mandua...")
    embeddings = {}
    for tabla in ("mandua_materiales", "mandua_mano_obra", "mandua_costeo"):
        embeddings[tabla] = cargar_embeddings_mandua(client, tabla, conn)

    # --- Limpiar mapeos previos del prototipo ---
    conn.execute("DELETE FROM mapeos_tcpo_mandua")
    conn.commit()

    # --- Matching ---
    print("\nEjecutando matching...")
    resultados = []
    stats = {"exacto": 0, "fuzzy": 0, "embedding": 0, "sin_match": 0}
    stats_clase = {}  # clase -> [total, matcheados]

    for item in tcpo_rows:
        tcpo_id      = item["id"]
        codigo       = item["codigo"]
        cls          = item["class"]
        desc_pt      = item["descripcion_pt"]
        desc_es      = item["descripcion_es"]
        subcapitulo  = item["subcapitulo"]

        # Clasificar SER.CG
        es_comp_aux = cls == "SER.CG" and es_composicion_auxiliar(subcapitulo, desc_pt)
        tipo_ser = "comp_aux" if es_comp_aux else "partida"
        clase_key = f"{cls} ({tipo_ser})" if cls == "SER.CG" else cls

        if clase_key not in stats_clase:
            stats_clase[clase_key] = [0, 0]
        stats_clase[clase_key][0] += 1

        tabla_destino = decidir_tabla_destino(cls, subcapitulo, desc_pt)
        cands = candidatos[tabla_destino]
        embs  = embeddings[tabla_destino]

        desc_norm = normalizar(desc_es)
        mandua_id = None
        confianza = None
        metodo    = None

        # Pasada 1: exacto
        r = match_exacto(desc_norm, cands)
        if r:
            mandua_id, confianza = r
            metodo = "exacto"
            stats["exacto"] += 1

        # Pasada 2: fuzzy
        if mandua_id is None:
            r = match_fuzzy(desc_norm, cands, umbral=FUZZY_UMBRAL)
            if r:
                mandua_id, confianza = r
                metodo = "fuzzy"
                stats["fuzzy"] += 1

        # Pasada 3: embedding
        if mandua_id is None:
            r = match_embedding(desc_es, embs, client, umbral=EMBED_UMBRAL)
            if r:
                mandua_id, confianza = r
                metodo = "embedding"
                stats["embedding"] += 1

        if mandua_id is None:
            stats["sin_match"] += 1

        if mandua_id is not None:
            stats_clase[clase_key][1] += 1
            mandua_tipo = TABLA_A_TIPO[tabla_destino]
            conn.execute(
                "INSERT INTO mapeos_tcpo_mandua "
                "(tcpo_item_id, mandua_tipo, mandua_id, confianza, metodo, fecha_mapeo) "
                "VALUES (?,?,?,?,?,?)",
                (tcpo_id, mandua_tipo, mandua_id, confianza, metodo, datetime.now().isoformat()),
            )

        resultados.append({
            "codigo":   codigo,
            "class":    cls,
            "tipo_ser": tipo_ser if cls == "SER.CG" else "-",
            "tabla":    tabla_destino.replace("mandua_", ""),
            "match":    "SI" if mandua_id else "NO",
            "metodo":   metodo or "-",
            "conf":     str(confianza) if confianza else "-",
        })

    conn.commit()

    # --- Tabla de resultados ---
    print()
    w = [14, 6, 9, 11, 5, 9, 5]
    header = ["Codigo", "Class", "Tipo SER", "Tabla", "Match", "Metodo", "Conf"]
    sep    = "  ".join("-" * wi for wi in w)
    head   = "  ".join(_col(h, wi) for h, wi in zip(header, w))
    print(sep)
    print(head)
    print(sep)
    for r in resultados:
        vals = [r["codigo"], r["class"], r["tipo_ser"], r["tabla"],
                r["match"], r["metodo"], r["conf"]]
        print("  ".join(_col(v, wi) for v, wi in zip(vals, w)))
    print(sep)

    # --- Estadisticas ---
    total = len(resultados)
    matcheados = stats["exacto"] + stats["fuzzy"] + stats["embedding"]
    print(f"\nTotal procesados : {total}")
    print(f"Matcheados exacto    : {stats['exacto']}")
    print(f"Matcheados fuzzy     : {stats['fuzzy']}")
    print(f"Matcheados embedding : {stats['embedding']}")
    print(f"Sin match            : {stats['sin_match']}")
    if matcheados < 20:
        print(f"  WARNING: solo {matcheados}/30 matcheados (minimo esperado: 20)")

    print("\nDesglose por clase TCPO:")
    for clase_k, (tot, mat) in sorted(stats_clase.items()):
        pct = int(mat / tot * 100) if tot else 0
        print(f"  {clase_k:<30} {mat}/{tot} ({pct}%)")

    # --- Query de verificacion ---
    print("\n--- Verificacion: mapeos_tcpo_mandua ---")
    print(f"{'Codigo':<22}  {'Class':<6}  {'Metodo':<9}  {'Conf':>4}  {'Tipo':<10}  Descripcion ES")
    print("-" * 100)
    for row in conn.execute(
        "SELECT t.codigo, t.class, t.descripcion_es, "
        "       m.metodo, m.confianza, m.mandua_tipo "
        "FROM tcpo_items t "
        "JOIN mapeos_tcpo_mandua m ON m.tcpo_item_id = t.id "
        "WHERE t.descripcion_es IS NOT NULL "
        "ORDER BY t.codigo"
    ):
        desc = (row["descripcion_es"] or "")[:55]
        tipo = row["mandua_tipo"] or "costeo"
        print(
            f"{row['codigo']:<22}  {row['class']:<6}  "
            f"{row['metodo']:<9}  {str(row['confianza']):>4}  "
            f"{tipo:<10}  {desc}"
        )

    conn.close()


if __name__ == "__main__":
    main()
