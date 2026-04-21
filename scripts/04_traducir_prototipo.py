"""04_traducir_prototipo.py - Traducción prototipo: 30 SER.CG de Alvenarias."""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import ROOT
from src.db import get_connection
from src.gemini_client import init_gemini, traducir_lote, hash_texto, MODEL_NAME
from src.cache_traducciones import get_cached, set_cached

CAPITULO = "06. Alvenarias, fechamentos e divisórias"
GLOSARIO_PATH = ROOT / "data" / "glosarios" / "glosario_construccion_py.json"
LIMIT = 30


def main():
    # Load glosario
    with open(GLOSARIO_PATH, encoding="utf-8") as f:
        glosario = json.load(f)
    print(f"Glosario cargado: {len(glosario['terminos'])} términos (v{glosario['version']})")

    # Fetch 30 unique SER.CG descriptions from Alvenarias
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, descripcion_pt, fila_original "
        "FROM tcpo_items "
        "WHERE capitulo = ? AND class = 'SER.CG' "
        "LIMIT ?",
        (CAPITULO, LIMIT),
    ).fetchall()

    if not rows:
        print(f"ERROR: no se encontraron filas con capitulo='{CAPITULO}'")
        conn.close()
        return

    print(f"\nPartidas encontradas: {len(rows)}")

    # Split into cached / uncached
    ids, descripciones = [], []
    for r in rows:
        ids.append(r["id"])
        descripciones.append(r["descripcion_pt"])

    hashes = [hash_texto(d) for d in descripciones]
    cached_map: dict[str, str] = {}
    pending_idx: list[int] = []

    for i, h in enumerate(hashes):
        cached = get_cached(h)
        if cached is not None:
            cached_map[h] = cached
        else:
            pending_idx.append(i)

    print(f"En caché: {len(cached_map)}  |  A traducir: {len(pending_idx)}")

    # Call Gemini for uncached items
    if pending_idx:
        client = init_gemini()
        pending_descs = [descripciones[i] for i in pending_idx]
        print(f"\nEnviando {len(pending_descs)} descripciones a {MODEL_NAME}...")
        traducciones = traducir_lote(pending_descs, glosario, client=client)
        print("Respuesta recibida OK.")

        for local_i, global_i in enumerate(pending_idx):
            h = hashes[global_i]
            trad = traducciones[local_i]
            set_cached(h, descripciones[global_i], trad, MODEL_NAME)
            cached_map[h] = trad

    # Build final list and update DB
    resultado: list[tuple[str, str]] = []
    update_batch = []
    for i, (item_id, desc, h) in enumerate(zip(ids, descripciones, hashes)):
        trad = cached_map[h]
        resultado.append((desc, trad))
        update_batch.append((trad, item_id))

    with conn:
        conn.executemany(
            "UPDATE tcpo_items SET descripcion_es = ? WHERE id = ?",
            update_batch,
        )
    print(f"\n{len(update_batch)} filas actualizadas en tcpo_items.")

    # Print comparison table
    col_w = 65
    sep = "-" * col_w
    print(f"\n{sep}  {sep}")
    print(f"{'DESCRIPCION PT':<{col_w}}  {'DESCRIPCION ES':<{col_w}}")
    print(f"{sep}  {sep}")
    for pt, es in resultado:
        pt_s = (pt[:col_w-1] + "…") if len(pt) > col_w else pt
        es_s = (es[:col_w-1] + "…") if len(es) > col_w else es
        print(f"{pt_s:<{col_w}}  {es_s:<{col_w}}")
    print(f"{sep}  {sep}")

    # Required verification query
    print(f"\n--- Query: tcpo_items con descripcion_es NOT NULL ---")
    for row in conn.execute(
        "SELECT descripcion_pt, descripcion_es FROM tcpo_items "
        "WHERE descripcion_es IS NOT NULL LIMIT 30"
    ):
        print(f"  PT: {row['descripcion_pt']}")
        print(f"  ES: {row['descripcion_es']}")
        print()

    conn.close()


if __name__ == "__main__":
    main()
