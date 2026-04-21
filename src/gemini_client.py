"""Cliente Gemini para traducción técnica PT→ES Paraguay."""
import json
import re
import time
import hashlib

from google import genai
from google.genai import types

from src.config import GEMINI_API_KEY

MODEL_NAME = "gemini-2.5-flash"
MAX_RETRIES = 3

_PROMPT_TEMPLATE = """\
Sos un experto traductor técnico de construcción. Traducís descripciones de ítems \
constructivos del portugués brasileño al español de Paraguay, respetando ESTRICTAMENTE \
el glosario provisto.

REGLAS:
1. Usá SIEMPRE las equivalencias del glosario cuando aparezcan
2. Mantené números, medidas y códigos sin cambiar (ej: "Ø 6 mm", "1,20 x 2,40 m", "fck=25 MPa")
3. Mantené marcas registradas sin traducir (ej: MACCAFERRI, Garelli, STECK, NBR)
4. No agregues explicaciones, solo traduce
5. Respondé SOLO un JSON array con las traducciones en el MISMO ORDEN que las descripciones originales

GLOSARIO:
{glosario_formateado}

DESCRIPCIONES A TRADUCIR:
{descripciones_numeradas}

Respondé SOLO el JSON array, sin markdown fence, sin texto adicional.\
"""


def init_gemini() -> genai.Client:
    return genai.Client(api_key=GEMINI_API_KEY)


def hash_texto(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def _fmt_glosario(glosario: dict) -> str:
    lines = [f"{t['pt']} = {t['es']}" for t in glosario.get("terminos", [])]
    return "\n".join(lines)


def _fmt_descripciones(descripciones: list[str]) -> str:
    return "\n".join(f"{i+1}. {d}" for i, d in enumerate(descripciones))


def _parse_json_array(text: str) -> list[str]:
    """Strip optional markdown fences and parse JSON array."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    result = json.loads(text.strip())
    if not isinstance(result, list):
        raise ValueError(f"Gemini devolvio un objeto en vez de array: {text[:200]}")
    return [str(x) for x in result]


def traducir_lote(
    descripciones: list[str],
    glosario: dict,
    client: genai.Client | None = None,
) -> list[str]:
    """Translate a batch of PT descriptions to ES using Gemini.

    Returns a list of ES strings in the same order as the input.
    Retries up to MAX_RETRIES times with exponential backoff.
    """
    if not descripciones:
        return []

    if client is None:
        client = init_gemini()

    prompt = _PROMPT_TEMPLATE.format(
        glosario_formateado=_fmt_glosario(glosario),
        descripciones_numeradas=_fmt_descripciones(descripciones),
    )

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.1,
    )

    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=config,
            )
            translations = _parse_json_array(response.text)
            if len(translations) != len(descripciones):
                raise ValueError(
                    f"Gemini devolvio {len(translations)} traducciones "
                    f"pero se enviaron {len(descripciones)}"
                )
            return translations
        except Exception as exc:
            last_exc = exc
            if attempt < MAX_RETRIES - 1:
                wait = 2 ** attempt
                print(f"  Intento {attempt+1} fallido: {exc}. Reintentando en {wait}s...")
                time.sleep(wait)

    raise RuntimeError(f"Gemini fallo tras {MAX_RETRIES} intentos") from last_exc
