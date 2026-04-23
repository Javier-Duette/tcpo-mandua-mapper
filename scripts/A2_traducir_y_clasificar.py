"""A2_traducir_y_clasificar.py - Traduccion + clasificacion de relevancia para Paraguay.

Uso:
  python scripts/A2_traducir_y_clasificar.py --prioridad alta --dry-run
  python scripts/A2_traducir_y_clasificar.py --prioridad alta --limit 100
  python scripts/A2_traducir_y_clasificar.py --prioridad alta
  python scripts/A2_traducir_y_clasificar.py --solo-clasificar --prioridad alta
"""
import argparse
import json
import logging
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tqdm import tqdm
from google.genai import types

from src.config import ROOT
from src.db import get_connection
from src.gemini_client import init_gemini, hash_texto, MODEL_NAME

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

BATCH_SIZE      = 40
RATE_LIMIT_S    = 0.5
CHECKPOINT_EVERY = 5
MAX_RETRIES     = 3
PREVIEW_N       = 5

# ---------------------------------------------------------------------------
# Prompts (UTF-8 — solo se envian a la API, nunca se imprime a consola)
# ---------------------------------------------------------------------------

_PROMPT_FULL = """\
Sos un traductor técnico especializado en construcción civil paraguaya.
Traducís descripciones del catálogo TCPO (Brasil) al español de Paraguay
Y clasificás la relevancia para obras residenciales en Paraguay.

GLOSARIO PT->ES (aplicar siempre que aparezca el término exacto):
{glosario}

REGLAS DE TRADUCCIÓN:
1. Aplicar el glosario
2. Mantener sin cambiar: códigos (fck=25 MPa, ø6 mm, NBR 6118), marcas registradas, medidas con unidades
3. Términos sin equivalente en PY: conservar en portugués
4. Máximo 70 caracteres por traducción

RELEVANCIA PARA PARAGUAY (elegir exactamente uno):
- alta     : se usa en construcción residencial paraguaya típica
- media    : aplica en obras PY pero no en toda residencial
- baja     : raro o costoso de implementar en Paraguay
- no_aplica: no se usa en PY (marcas/normas exclusivamente brasileñas, técnicas no adoptadas en PY)

FORMATO DE RESPUESTA: JSON array SOLAMENTE. Sin markdown, sin texto adicional.
[{{"n":1,"es":"traducción","relevancia":"alta","justificacion":"motivo max 12 palabras"}},{{"n":2,"es":"otra","relevancia":"media","justificacion":"motivo"}}]

DESCRIPCIONES A PROCESAR ({n} items):
{items}
"""

_PROMPT_SOLO_TRADUCIR = """\
Sos un traductor técnico de construcción civil. Traducís el catálogo TCPO (Brasil)
al español de Paraguay.

GLOSARIO PT->ES:
{glosario}

REGLAS:
1. Aplicar el glosario
2. Mantener sin cambiar: códigos, marcas registradas, medidas con unidades
3. Máximo 70 caracteres por traducción

FORMATO DE RESPUESTA: JSON array SOLAMENTE. Sin markdown, sin texto adicional.
[{{"n":1,"es":"traducción"}},{{"n":2,"es":"otra traducción"}}]

DESCRIPCIONES A TRADUCIR ({n} items):
{items}
"""

_PROMPT_SOLO_CLASIFICAR = """\
Sos un experto en construcción civil paraguaya.
Clasificás la relevancia de ítems del catálogo TCPO para obras residenciales en Paraguay.
Cada ítem se presenta como "DESCRIPCION PT | DESCRIPCION ES".

RELEVANCIA (elegir exactamente uno):
- alta     : construcción residencial paraguaya típica
- media    : aplica en obras PY pero no en toda residencial
- baja     : raro o costoso en Paraguay
- no_aplica: no se usa en PY (marcas/normas exclusivamente brasileñas, técnicas no adoptadas)

FORMATO DE RESPUESTA: JSON array SOLAMENTE. Sin markdown, sin texto adicional.
[{{"n":1,"relevancia":"alta","justificacion":"motivo max 12 palabras"}},{{"n":2,"relevancia":"media","justificacion":"motivo"}}]

ÍTEMS A CLASIFICAR ({n} items):
{items}
"""


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def _setup_logging() -> logging.Logger:
    logs_dir = ROOT / "logs"
    logs_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    log_path = logs_dir / f"traduccion_{ts}.log"
    logger = logging.getLogger("a2")
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(fh)
    print(f"Log: {log_path}")
    return logger


def _extend_cache_schema(conn) -> None:
    """Agrega metadata_json a traducciones_cache si no existe."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(traducciones_cache)").fetchall()}
    if "metadata_json" not in cols:
        conn.execute("ALTER TABLE traducciones_cache ADD COLUMN metadata_json TEXT")
        conn.commit()
        print("  [OK] traducciones_cache.metadata_json agregado")


def _cargar_glosario_str(conn) -> str:
    """Retorna glosario formateado 'pt = es' para incluir en prompt."""
    rows = conn.execute(
        "SELECT termino_pt, termino_es FROM glosario_terminos ORDER BY termino_pt"
    ).fetchall()
    if rows:
        lines = [f"{r['termino_pt']} = {r['termino_es']}" for r in rows]
        print(f"  Glosario: {len(lines)} terminos (DB)")
        return "\n".join(lines)
    # Fallback JSON
    json_path = ROOT / "data" / "glosarios" / "glosario_construccion_py.json"
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    terminos = data.get("terminos", [])
    lines = [f"{t['pt']} = {t['es']}" for t in terminos]
    print(f"  Glosario: {len(lines)} terminos (JSON fallback)")
    return "\n".join(lines)


def _cargar_capitulos(prioridad: str, capitulos_override: list | None) -> list[str]:
    if capitulos_override:
        return [c.zfill(2) for c in capitulos_override]
    config_path = ROOT / "data" / "capitulos_relevantes_py.json"
    with open(config_path, encoding="utf-8") as f:
        cfg = json.load(f)
    if prioridad == "alta":
        return cfg["capitulos_alta_prioridad"]
    if prioridad == "media":
        return cfg["capitulos_alta_prioridad"] + cfg["capitulos_media_prioridad"]
    return (cfg["capitulos_alta_prioridad"] +
            cfg["capitulos_media_prioridad"] +
            cfg.get("capitulos_baja_prioridad", []))


def _get_pendientes(conn, capitulos: list[str], limit: int | None, modo: str) -> list[dict]:
    """Retorna lista de {pt, es, hash} — una entrada por descripcion_pt distinta."""
    phs = ",".join("?" for _ in capitulos)
    if modo == "solo_clasificar":
        sql = f"""
            SELECT descripcion_pt, MAX(descripcion_es) AS descripcion_es
            FROM tcpo_items
            WHERE descripcion_es IS NOT NULL
              AND relevancia_py = 'sin_clasificar'
              AND class IS NOT NULL
              AND SUBSTR(capitulo, 1, 2) IN ({phs})
            GROUP BY descripcion_pt
            {"LIMIT ?" if limit else ""}
        """
    else:
        sql = f"""
            SELECT descripcion_pt
            FROM tcpo_items
            WHERE descripcion_es IS NULL
              AND class IS NOT NULL
              AND SUBSTR(capitulo, 1, 2) IN ({phs})
            GROUP BY descripcion_pt
            {"LIMIT ?" if limit else ""}
        """
    params = list(capitulos) + ([limit] if limit else [])
    rows = conn.execute(sql, params).fetchall()
    result = []
    for r in rows:
        pt = r["descripcion_pt"] or ""
        es = r["descripcion_es"] if modo == "solo_clasificar" else None
        result.append({"pt": pt, "es": es, "hash": hash_texto(pt)})
    return result


# ---------------------------------------------------------------------------
# Cache helpers (usa columna metadata_json)
# ---------------------------------------------------------------------------

def _get_cached(conn, h: str) -> dict | None:
    row = conn.execute(
        "SELECT texto_traducido, metadata_json "
        "FROM traducciones_cache WHERE hash_original = ?",
        (h,),
    ).fetchone()
    if row is None:
        return None
    es   = row["texto_traducido"] or None
    meta = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
    return {
        "es":           es,
        "relevancia":   meta.get("relevancia"),
        "justificacion": meta.get("justificacion"),
    }


def _set_cached(conn, h: str, pt: str, es: str | None,
                relevancia: str | None, justificacion: str | None) -> None:
    meta = {}
    if relevancia:
        meta["relevancia"] = relevancia
    if justificacion:
        meta["justificacion"] = justificacion
    conn.execute(
        "INSERT OR REPLACE INTO traducciones_cache "
        "(hash_original, texto_original, texto_traducido, modelo_usado, "
        " fecha_traduccion, metadata_json) "
        "VALUES (?,?,?,?,?,?)",
        (h, pt, es or "", MODEL_NAME,
         datetime.now().isoformat(),
         json.dumps(meta) if meta else None),
    )


def _cache_valido(cached: dict | None, modo: str) -> bool:
    if cached is None:
        return False
    if modo in ("full", "solo_traducir") and not cached.get("es"):
        return False
    if modo in ("full", "solo_clasificar") and not cached.get("relevancia"):
        return False
    return True


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------

def _build_prompt(descs: list[dict], glosario_str: str, modo: str) -> str:
    if modo == "solo_clasificar":
        items_txt = "\n".join(
            f"{i+1}. {d['pt']} | {d['es'] or ''}"
            for i, d in enumerate(descs)
        )
        return _PROMPT_SOLO_CLASIFICAR.format(n=len(descs), items=items_txt)
    items_txt = "\n".join(f"{i+1}. {d['pt']}" for i, d in enumerate(descs))
    if modo == "solo_traducir":
        return _PROMPT_SOLO_TRADUCIR.format(
            glosario=glosario_str, n=len(descs), items=items_txt
        )
    return _PROMPT_FULL.format(
        glosario=glosario_str, n=len(descs), items=items_txt
    )


def _parse_respuesta(text: str, n_esperado: int, modo: str) -> list[dict]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    arr = json.loads(text.strip())
    if not isinstance(arr, list):
        raise ValueError(f"Respuesta no es array: {type(arr)}")
    if len(arr) != n_esperado:
        raise ValueError(f"Array tiene {len(arr)} items, esperado {n_esperado}")
    results = []
    for item in arr:
        r: dict = {}
        if modo != "solo_clasificar":
            r["es"] = str(item.get("es", "")).strip() or None
        else:
            r["es"] = None
        if modo != "solo_traducir":
            rel = item.get("relevancia", "sin_clasificar")
            if rel not in ("alta", "media", "baja", "no_aplica"):
                rel = "sin_clasificar"
            r["relevancia"]    = rel
            r["justificacion"] = str(item.get("justificacion", "")).strip() or None
        else:
            r["relevancia"]    = None
            r["justificacion"] = None
        results.append(r)
    return results


def _llamar_gemini(
    descs: list[dict], glosario_str: str, client, modo: str, logger
) -> tuple[list[dict], int, int]:
    """Llama Gemini con reintentos. Retorna (results, tok_in, tok_out)."""
    prompt = _build_prompt(descs, glosario_str, modo)
    cfg    = types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.1,
    )
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            resp    = client.models.generate_content(
                model=MODEL_NAME, contents=prompt, config=cfg
            )
            results = _parse_respuesta(resp.text, len(descs), modo)
            usage   = resp.usage_metadata
            tok_in  = getattr(usage, "prompt_token_count",     0) or 0
            tok_out = getattr(usage, "candidates_token_count", 0) or 0
            return results, tok_in, tok_out
        except Exception as exc:
            last_exc = exc
            logger.warning(f"Intento {attempt+1}/{MAX_RETRIES}: {exc}")
            if attempt < MAX_RETRIES - 1:
                wait = 2 ** attempt
                print(f"  Reintentando en {wait}s...")
                time.sleep(wait)
    raise RuntimeError(f"Gemini fallo tras {MAX_RETRIES} intentos") from last_exc


# ---------------------------------------------------------------------------
# DB update
# ---------------------------------------------------------------------------

def _update_tcpo(conn, descs: list[dict], results: list[dict],
                 modo: str, ts: str) -> None:
    if modo in ("full", "solo_traducir"):
        rows = [
            (r.get("es"), ts, d["pt"])
            for d, r in zip(descs, results)
            if r.get("es")
        ]
        if rows:
            conn.executemany(
                "UPDATE tcpo_items "
                "SET descripcion_es=?, fecha_traduccion=? "
                "WHERE descripcion_pt=?",
                rows,
            )
    if modo in ("full", "solo_clasificar"):
        rows = [
            (r["relevancia"], r.get("justificacion"), ts, d["pt"])
            for d, r in zip(descs, results)
            if r.get("relevancia") and r["relevancia"] != "sin_clasificar"
        ]
        if rows:
            conn.executemany(
                "UPDATE tcpo_items "
                "SET relevancia_py=?, relevancia_justificacion=?, fecha_clasificacion=? "
                "WHERE descripcion_pt=?",
                rows,
            )


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------

def _mostrar_preview(descs: list[dict], results: list[dict], modo: str) -> None:
    print()
    print("--- PREVIEW (primeros 5 items) ---")
    for i, (d, r) in enumerate(zip(descs, results)):
        print(f"[{i+1}] PT: {d['pt'][:80]}")
        if r.get("es"):
            print(f"     ES: {r['es'][:80]}")
        if r.get("relevancia"):
            just = (r.get("justificacion") or "")[:60]
            print(f"     Relevancia: {r['relevancia']} - {just}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Traducir y clasificar items TCPO")
    parser.add_argument("--prioridad",      choices=["alta", "media", "todos"], default="alta")
    parser.add_argument("--capitulos",      nargs="+", default=None,
                        help="Codigos de capitulo (ej: 05 06). Anula --prioridad.")
    parser.add_argument("--limit",          type=int, default=None,
                        help="Max items unicos a procesar")
    parser.add_argument("--dry-run",        action="store_true",
                        help="Muestra plan sin llamar a la API")
    parser.add_argument("--solo-traducir",  action="store_true",
                        help="Solo actualiza descripcion_es, omite relevancia")
    parser.add_argument("--solo-clasificar", action="store_true",
                        help="Solo actualiza relevancia_py (items ya traducidos)")
    args = parser.parse_args()

    if args.solo_traducir and args.solo_clasificar:
        print("ERROR: --solo-traducir y --solo-clasificar son mutuamente excluyentes")
        sys.exit(1)

    modo = "full"
    if args.solo_traducir:
        modo = "solo_traducir"
    elif args.solo_clasificar:
        modo = "solo_clasificar"

    logger = _setup_logging()
    logger.info(f"Inicio A2: modo={modo} prioridad={args.prioridad} "
                f"limit={args.limit} dry_run={args.dry_run}")

    conn = get_connection()
    _extend_cache_schema(conn)
    glosario_str = _cargar_glosario_str(conn)
    capitulos    = _cargar_capitulos(args.prioridad, args.capitulos)

    print(f"Capitulos ({len(capitulos)}): {', '.join(capitulos)}")

    pendientes = _get_pendientes(conn, capitulos, args.limit, modo)
    print(f"Items unicos pendientes : {len(pendientes)}")

    # --- Dry run ---
    if args.dry_run:
        n         = len(pendientes)
        n_batches = (n + BATCH_SIZE - 1) // BATCH_SIZE
        est_tok   = n * 250
        est_usd   = est_tok * 0.50 / 750_000
        print()
        print("=== DRY RUN ===")
        print(f"  Items a procesar : {n:,}")
        print(f"  Batches (N={BATCH_SIZE})  : {n_batches}")
        print(f"  Tokens estimados : {est_tok:,}")
        print(f"  Costo estimado   : USD {est_usd:.3f}")
        print(f"  Modo             : {modo}")
        print()
        print("  Muestra (primeros 10):")
        for i, d in enumerate(pendientes[:10]):
            print(f"    {i+1:3}. {d['pt'][:80]}")
        logger.info(f"Dry run: {n} pendientes, est USD {est_usd:.3f}")
        conn.close()
        return

    # --- Init Gemini ---
    client = init_gemini()

    # --- Preview 5 items ---
    preview_descs = pendientes[:PREVIEW_N]
    print(f"Procesando preview ({len(preview_descs)} items)...")
    try:
        prev_results, _, _ = _llamar_gemini(
            preview_descs, glosario_str, client, modo, logger
        )
        _mostrar_preview(preview_descs, prev_results, modo)
        for d, r in zip(preview_descs, prev_results):
            _set_cached(conn, d["hash"], d["pt"],
                        r.get("es"), r.get("relevancia"), r.get("justificacion"))
        conn.commit()
    except Exception as exc:
        print(f"ERROR en preview: {exc}")
        logger.error(f"Preview fallido: {exc}")
        conn.close()
        sys.exit(1)

    respuesta = input("Continuar con el resto? [y/N]: ").strip().lower()
    if respuesta != "y":
        print("Cancelado.")
        conn.close()
        return

    # --- Bucle principal ---
    total_tok_in  = 0
    total_tok_out = 0
    n_ok          = 0
    n_fallidos    = 0
    batch_count   = 0
    ts_now        = datetime.now().isoformat()
    dist_rel: dict[str, int] = {
        "alta": 0, "media": 0, "baja": 0, "no_aplica": 0, "sin_clasificar": 0
    }

    with tqdm(total=len(pendientes), ascii=True, desc="Procesando", unit="item") as pbar:
        for i in range(0, len(pendientes), BATCH_SIZE):
            batch = pendientes[i : i + BATCH_SIZE]

            # Separar cached / uncached
            cached_map: dict[str, dict] = {}
            uncached: list[dict] = []
            for d in batch:
                c = _get_cached(conn, d["hash"])
                if _cache_valido(c, modo):
                    cached_map[d["hash"]] = c
                else:
                    uncached.append(d)

            # Llamar Gemini para los no cacheados
            gemini_map: dict[str, dict] = {}
            if uncached:
                try:
                    raw, tok_in, tok_out = _llamar_gemini(
                        uncached, glosario_str, client, modo, logger
                    )
                    total_tok_in  += tok_in
                    total_tok_out += tok_out
                    for d, r in zip(uncached, raw):
                        gemini_map[d["hash"]] = r
                        _set_cached(conn, d["hash"], d["pt"],
                                    r.get("es"), r.get("relevancia"),
                                    r.get("justificacion"))
                    time.sleep(RATE_LIMIT_S)
                except Exception as exc:
                    logger.error(f"Batch {batch_count} fallido: {exc}")
                    print(f"\n  WARNING: batch {batch_count} fallido ({exc})")
                    n_fallidos += len(uncached)
                    pbar.update(len(batch))
                    batch_count += 1
                    continue

            # Merge resultados y actualizar DB
            all_results: list[dict] = []
            for d in batch:
                r = cached_map.get(d["hash"]) or gemini_map.get(d["hash"]) or {}
                all_results.append(r)
                rel = (r.get("relevancia") or "sin_clasificar")
                if rel in dist_rel:
                    dist_rel[rel] += 1

            _update_tcpo(conn, batch, all_results, modo, ts_now)
            n_ok += len(batch) - len([r for r in all_results if not r])
            batch_count += 1

            if batch_count % CHECKPOINT_EVERY == 0:
                conn.commit()
                logger.info(f"Checkpoint batch={batch_count} ok={n_ok}")

            pbar.update(len(batch))

    conn.commit()

    # --- Resumen ---
    est_usd = (total_tok_in * 0.075 + total_tok_out * 0.30) / 1_000_000
    print()
    print("=== RESUMEN SESION A2 ===")
    print(f"  Modo            : {modo}")
    print(f"  Items procesados: {n_ok + n_fallidos:,}")
    print(f"  Fallidos        : {n_fallidos}")
    print(f"  Tokens entrada  : {total_tok_in:,}")
    print(f"  Tokens salida   : {total_tok_out:,}")
    print(f"  Costo estimado  : USD {est_usd:.4f}")
    print()
    print("  Distribucion de relevancia (items unicos procesados esta sesion):")
    for rel, cnt in dist_rel.items():
        if cnt > 0:
            bar = "#" * min(cnt // 5, 40)
            print(f"    {rel:<12}: {cnt:5d}  {bar}")

    # --- Queries de verificacion ---
    print()
    print("--- Verificacion: tcpo_items con traduccion ---")
    print(f"  {'Capitulo':<50}  {'Relevancia':<12}  N")
    print("  " + "-" * 78)
    for row in conn.execute("""
        SELECT capitulo, relevancia_py, COUNT(*) AS n
        FROM tcpo_items
        WHERE descripcion_es IS NOT NULL
        GROUP BY capitulo, relevancia_py
        ORDER BY capitulo, relevancia_py
    """):
        cap = (row["capitulo"] or "")[:48]
        print(f"  {cap:<50}  {row['relevancia_py'] or '':<12}  {row['n']}")

    n_no_aplica = conn.execute(
        "SELECT COUNT(*) FROM tcpo_items WHERE relevancia_py='no_aplica'"
    ).fetchone()[0]
    print(f"\n  Total no_aplica: {n_no_aplica}")

    print("\n  Muestra no_aplica (hasta 10):")
    for row in conn.execute(
        "SELECT descripcion_es, relevancia_justificacion "
        "FROM tcpo_items WHERE relevancia_py='no_aplica' LIMIT 10"
    ):
        desc = (row["descripcion_es"] or "")[:55]
        just = (row["relevancia_justificacion"] or "")[:40]
        print(f"    {desc:<55}  {just}")

    conn.close()
    logger.info(
        f"A2 completado: modo={modo} ok={n_ok} fallidos={n_fallidos} "
        f"tok_in={total_tok_in} tok_out={total_tok_out} usd={est_usd:.4f}"
    )


if __name__ == "__main__":
    main()
