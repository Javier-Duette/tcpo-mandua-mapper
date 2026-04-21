"""Funciones de matching TCPO -> Mandua (estrategia estratificada D-003)."""
import re

from rapidfuzz import fuzz, process
from unidecode import unidecode as _unidecode

_PALABRAS_COMPOSICION = {"argamassa", "concreto", "chapisco", "graute", "mortero"}

# Maps tabla name to the mandua_tipo value used in mapeos_tcpo_mandua.
# mandua_costeo uses None because 'costeo' no esta en el CHECK del schema.
TABLA_A_TIPO = {
    "mandua_materiales": "material",
    "mandua_mano_obra": "mano_obra",
    "mandua_costeo": None,
}


def normalizar(texto: str) -> str:
    if not texto:
        return ""
    s = _unidecode(str(texto)).lower()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def es_composicion_auxiliar(
    subcapitulo: str | None,
    descripcion_pt: str | None,
) -> bool:
    """True si el item SER.CG es una composicion auxiliar (argamassa, concreto, etc.)."""
    # (a) subcapitulo contiene alguna palabra clave
    if subcapitulo:
        sub_norm = normalizar(subcapitulo)
        if any(p in sub_norm for p in _PALABRAS_COMPOSICION):
            return True
    # (b) descripcion_pt empieza con alguna palabra clave (primeros 20 chars)
    if descripcion_pt:
        prefix = normalizar(descripcion_pt[:20])
        if any(prefix.startswith(p) for p in _PALABRAS_COMPOSICION):
            return True
    return False


def decidir_tabla_destino(
    class_tcpo: str,
    subcapitulo: str | None,
    descripcion_pt: str | None,
) -> str:
    """Retorna la tabla mandua destino segun la logica D-003."""
    if class_tcpo == "MAT.":
        return "mandua_materiales"
    if class_tcpo == "M.O.":
        return "mandua_mano_obra"
    if class_tcpo == "SER.CG":
        if es_composicion_auxiliar(subcapitulo, descripcion_pt):
            return "mandua_materiales"
        return "mandua_costeo"
    # Otros class (SER.CH, EQ.AQ., DIVER, etc.) -> materiales por defecto
    return "mandua_materiales"


def match_exacto(
    desc_norm: str,
    candidates: list,
) -> tuple[int, int] | None:
    """Retorna (mandua_id, confianza=100) si hay coincidencia exacta normalizada."""
    for c in candidates:
        cn = c["descripcion_normalizada"]
        if cn and cn == desc_norm:
            return c["id"], 100
    return None


def match_fuzzy(
    desc_norm: str,
    candidates: list,
    umbral: int = 75,
) -> tuple[int, int] | None:
    """Retorna (mandua_id, confianza) via token_set_ratio si supera umbral."""
    choices = {c["id"]: (c["descripcion_normalizada"] or "") for c in candidates}
    if not choices:
        return None
    result = process.extractOne(
        desc_norm,
        choices,
        scorer=fuzz.token_set_ratio,
        score_cutoff=umbral,
    )
    if result is not None:
        _val, score, key = result
        return key, int(score)
    return None


def match_embedding(
    desc_es: str,
    mandua_embeddings: dict[str, list[float]],
    client,
    umbral: float = 0.70,
) -> tuple[int, int] | None:
    """Retorna (mandua_id, confianza) via similitud coseno si supera umbral."""
    from src.embeddings import get_embedding_gemini, similitud_coseno

    if not mandua_embeddings:
        return None
    try:
        tcpo_vec = get_embedding_gemini(desc_es, client)
    except Exception as exc:
        print(f"  WARNING: embedding fallido para '{desc_es[:50]}': {exc}")
        return None

    best_id: str | None = None
    best_sim = 0.0
    for mid, mvec in mandua_embeddings.items():
        sim = similitud_coseno(tcpo_vec, mvec)
        if sim > best_sim:
            best_sim = sim
            best_id = mid

    if best_id is not None and best_sim >= umbral:
        return int(best_id), int(best_sim * 100)
    return None
