"""formatters.py — Formateo de números, precios e indicadores visuales."""

_REL_EMOJI = {
    "alta":          "🟢",
    "media":         "🟡",
    "baja":          "🟠",
    "no_aplica":     "🔴",
    "sin_clasificar":"⚪",
}

_REL_COLOR = {
    "alta":          "#28a745",
    "media":         "#ffc107",
    "baja":          "#fd7e14",
    "no_aplica":     "#dc3545",
    "sin_clasificar":"#adb5bd",
}

_CLASS_LABEL = {
    "SER.CG": "Servicio",
    "MAT.":   "Material",
    "M.O.":   "Mano de obra",
    "EQ.AQ.": "Equipo",
    "SER.CH": "Serv. hora",
    "DIVER":  "Diversos",
}


def relevancia_badge(r: str | None) -> str:
    r = r or "sin_clasificar"
    return f"{_REL_EMOJI.get(r, '⚪')} {r}"


def relevancia_color(r: str | None) -> str:
    return _REL_COLOR.get(r or "sin_clasificar", "#adb5bd")


def clase_label(c: str | None) -> str:
    return _CLASS_LABEL.get(c or "", c or "")


def fmt_gs(n) -> str:
    """Guaraníes: Gs. 1.234.567"""
    if n is None or (isinstance(n, float) and n != n):  # NaN
        return "—"
    try:
        return f"Gs. {int(n):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "—"


def fmt_brl(n) -> str:
    """Reais: R$ 1.234,56"""
    if n is None or (isinstance(n, float) and n != n):
        return "—"
    try:
        s = f"{float(n):,.2f}"
        parts = s.split(".")
        integer = parts[0].replace(",", ".")
        return f"R$ {integer},{parts[1]}"
    except (ValueError, TypeError):
        return "—"


def fmt_pct(n: float) -> str:
    return f"{n:.0f}%"


def fmt_coef(n) -> str:
    if n is None or (isinstance(n, float) and n != n):
        return "—"
    try:
        v = float(n)
        return f"{v:.4f}".rstrip("0").rstrip(".")
    except (ValueError, TypeError):
        return "—"


def truncar(s: str | None, maxlen: int = 60) -> str:
    if not s:
        return "—"
    return s if len(s) <= maxlen else s[: maxlen - 1] + "…"
