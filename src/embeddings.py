"""Embeddings via Gemini text-embedding-004 con cache JSON persistente."""
import json
import math
import time

from src.config import ROOT

EMBEDDING_MODEL = "text-embedding-004"
CACHE_PATH = ROOT / "data" / "traducciones" / "embeddings_mandua.json"
SAVE_EVERY = 50  # persistir cache cada N embeddings generados

_TABLA_TEXT_FIELD = {
    "mandua_materiales": "descripcion",
    "mandua_mano_obra": "descripcion",
    "mandua_costeo": "partida",
}


def get_embedding_gemini(texto: str, client) -> list[float]:
    """Llama a text-embedding-004 y retorna el vector."""
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=texto,
    )
    return result.embeddings[0].values


def similitud_coseno(v1: list[float], v2: list[float]) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    n1 = math.sqrt(sum(a * a for a in v1))
    n2 = math.sqrt(sum(b * b for b in v2))
    if n1 == 0.0 or n2 == 0.0:
        return 0.0
    return dot / (n1 * n2)


def _leer_cache() -> dict:
    if CACHE_PATH.exists():
        with open(CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _escribir_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f)


def cargar_embeddings_mandua(
    client,
    tabla: str,
    conn,
) -> dict[str, list[float]]:
    """Retorna {str(id): vector} para todas las filas de tabla.

    Lee del cache JSON si existe; genera los faltantes via Gemini y persiste.
    """
    from tqdm import tqdm

    cache = _leer_cache()
    tabla_cache: dict[str, list[float]] = cache.get(tabla, {})

    text_field = _TABLA_TEXT_FIELD.get(tabla, "descripcion")
    rows = conn.execute(f"SELECT id, {text_field} as texto FROM {tabla}").fetchall()

    pendientes = [
        (str(r["id"]), r["texto"])
        for r in rows
        if str(r["id"]) not in tabla_cache and r["texto"]
    ]

    if not pendientes:
        print(f"  Cache hit: {len(tabla_cache)} embeddings para {tabla}")
        return tabla_cache

    print(f"  Generando {len(pendientes)} embeddings para {tabla}...")
    generados = 0
    errores = 0

    for item_id, texto in tqdm(pendientes, desc=f"  {tabla[:20]}", ascii=True, leave=True):
        try:
            vec = get_embedding_gemini(texto, client)
            tabla_cache[item_id] = vec
            generados += 1
            time.sleep(0.65)
            if generados % SAVE_EVERY == 0:
                cache[tabla] = tabla_cache
                _escribir_cache(cache)
        except Exception as exc:
            errores += 1
            print(f"\n  WARNING: embedding fallido id={item_id}: {exc}")

    cache[tabla] = tabla_cache
    _escribir_cache(cache)
    print(f"  Generados: {generados}  Errores: {errores}  Cache: {len(tabla_cache)} total")
    return tabla_cache
