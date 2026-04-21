"""Caché de traducciones sobre la tabla traducciones_cache."""
from datetime import datetime

from src.db import get_connection
from src.gemini_client import MODEL_NAME


def get_cached(hash_original: str) -> str | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT texto_traducido FROM traducciones_cache WHERE hash_original = ?",
        (hash_original,),
    ).fetchone()
    conn.close()
    return row["texto_traducido"] if row else None


def set_cached(
    hash_original: str,
    original: str,
    traducido: str,
    modelo: str = MODEL_NAME,
) -> None:
    conn = get_connection()
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO traducciones_cache "
            "(hash_original, texto_original, texto_traducido, modelo_usado, fecha_traduccion) "
            "VALUES (?,?,?,?,?)",
            (hash_original, original, traducido, modelo, datetime.now().isoformat()),
        )
    conn.close()
