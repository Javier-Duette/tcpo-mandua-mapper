"""filtros.py — Panel de filtros reutilizable para el Explorador."""
import streamlit as st
from app.utils.queries import get_capitulos_con_conteo, get_subcapitulos

_RELEVANCIA_OPTS = ["alta", "media", "baja", "no_aplica", "sin_clasificar"]
_CLASE_OPTS      = ["SER.CG", "MAT.", "M.O.", "EQ.AQ.", "SER.CH", "DIVER"]


def panel_filtros(key_prefix: str = "f") -> dict:
    """
    Renderiza el panel de filtros en la columna izquierda.
    Retorna dict con los filtros activos.
    """
    df_caps = get_capitulos_con_conteo()

    st.markdown("### 📂 Capítulos")

    # Filtro rápido: solo alta prioridad con items alta relevancia
    solo_alta = st.checkbox(
        "Solo capítulos con ítems **alta** relevancia",
        key=f"{key_prefix}_solo_alta",
    )
    if solo_alta:
        df_caps = df_caps[df_caps["n_alta"] > 0]

    # Mostrar capítulos como lista con checkboxes
    cap_opciones = []
    for _, row in df_caps.iterrows():
        cap  = row["capitulo"] or ""
        n    = int(row["n_servicios"])
        alta = int(row["n_alta"])
        cap_opciones.append(f"{cap} ({n} svc, {alta}★)")

    caps_label_to_val = {
        f"{row['capitulo']} ({int(row['n_servicios'])} svc, {int(row['n_alta'])}★)": row["capitulo"]
        for _, row in df_caps.iterrows()
    }

    sel_labels = st.multiselect(
        "Seleccionar capítulos",
        options=list(caps_label_to_val.keys()),
        key=f"{key_prefix}_caps",
        placeholder="Todos los capítulos…",
    )
    capitulos_sel = [caps_label_to_val[l] for l in sel_labels]

    # Subcapítulos (dinámico según capítulos seleccionados)
    subcaps_sel: list[str] = []
    if capitulos_sel:
        subcaps_disponibles = get_subcapitulos(capitulos_sel)
        if subcaps_disponibles:
            subcaps_sel = st.multiselect(
                "Subcapítulos",
                options=subcaps_disponibles,
                key=f"{key_prefix}_subcaps",
                placeholder="Todos…",
            )

    st.divider()
    st.markdown("### 🔍 Filtros")

    relevancia_sel = st.multiselect(
        "Relevancia PY",
        options=_RELEVANCIA_OPTS,
        default=["alta", "media", "baja"],
        key=f"{key_prefix}_rel",
        format_func=lambda r: {"alta": "🟢 alta", "media": "🟡 media",
                                "baja": "🟠 baja", "no_aplica": "🔴 no aplica",
                                "sin_clasificar": "⚪ sin clasificar"}.get(r, r),
    )

    incluir_insumos = st.toggle(
        "Incluir insumos (MAT / M.O.)",
        value=False,
        key=f"{key_prefix}_insumos",
        help="Por defecto se muestran solo servicios (SER.CG)",
    )

    clases_sel: list[str] = []
    if incluir_insumos:
        clases_sel = st.multiselect(
            "Clases",
            options=_CLASE_OPTS,
            default=_CLASE_OPTS,
            key=f"{key_prefix}_clases",
        )

    solo_traducidos = st.checkbox(
        "Solo ítems traducidos",
        value=True,
        key=f"{key_prefix}_trad",
    )

    return {
        "capitulos":       capitulos_sel or None,
        "subcapitulos":    subcaps_sel or None,
        "relevancia":      relevancia_sel or None,
        "clases":          clases_sel or None,
        "solo_servicios":  not incluir_insumos,
        "solo_traducidos": solo_traducidos,
        "busqueda":        st.session_state.get(f"{key_prefix}_busqueda") or None,
    }
