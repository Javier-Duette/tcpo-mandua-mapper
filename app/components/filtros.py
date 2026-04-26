"""filtros.py — Panel de filtros rediseñado (Opción B)."""
import streamlit as st
from app.utils.queries import get_capitulos_con_conteo, get_subcapitulos, get_count_revision

_RELEVANCIA_OPTS = ["alta", "media", "baja", "no_aplica", "sin_clasificar"]
_RELEVANCIA_LABELS = {
    "alta":           "🟢 alta",
    "media":          "🟡 media",
    "baja":           "🟠 baja",
    "no_aplica":      "🔴 no aplica",
    "sin_clasificar": "⚪ sin clasificar",
}
_CLASE_OPTS = [
    "SER.CG", "MAT.", "M.O.", "EQ.AQ.",
    "SER.CH", "SER.MO", "DIVER", "EQ.LOC",
    "JUROS", "DEPRE", "MANUT", "EMPRE",
]


def panel_filtros(key_prefix: str = "f") -> dict:
    """Renderiza el panel de filtros. Retorna dict de filtros activos."""

    # Contador de versión para resetear todos los widgets con "Limpiar"
    vk = f"{key_prefix}_v"
    if vk not in st.session_state:
        st.session_state[vk] = 0
    v = st.session_state[vk]

    # ── Búsqueda ──────────────────────────────────────────────────────────────
    st.markdown("#### 🔍 Búsqueda")

    modo_busqueda = st.radio(
        "Buscar en",
        options=["Descripción", "Código", "Ambos"],
        horizontal=True,
        key=f"{key_prefix}_modo_{v}",
        index=0,
    )
    placeholders = {
        "Descripción": "ej: mampostería, concreto, impermeabilización…",
        "Código":      "ej: 06.101  o  04.108.000027  o  SER",
        "Ambos":       "ej: 06.101  o  alvenaria…",
    }
    busqueda = st.text_input(
        "Término de búsqueda",
        placeholder=placeholders[modo_busqueda],
        key=f"{key_prefix}_busq_{v}",
        label_visibility="collapsed",
    )

    st.divider()

    # ── Capítulo ──────────────────────────────────────────────────────────────
    st.markdown("#### 📂 Capítulo")

    df_caps = get_capitulos_con_conteo()
    solo_alta = st.toggle(
        "Solo capítulos con ítems de alta relevancia",
        key=f"{key_prefix}_solo_alta_{v}",
        value=False,
    )
    if solo_alta:
        df_caps = df_caps[df_caps["n_alta"] > 0]

    cap_labels = ["(Todos los capítulos)"] + [
        f"{row['capitulo']}  ·  {int(row['n_servicios'])} svc"
        for _, row in df_caps.iterrows()
    ]
    cap_values = [None] + list(df_caps["capitulo"])

    cap_idx = st.selectbox(
        "Capítulo",
        options=range(len(cap_labels)),
        format_func=lambda i: cap_labels[i],
        key=f"{key_prefix}_cap_{v}",
        label_visibility="collapsed",
    )
    capitulo_sel = cap_values[cap_idx]

    # Subcapítulo — dinámico según capítulo seleccionado
    subcapitulo_sel = None
    if capitulo_sel:
        subcaps_disponibles = get_subcapitulos([capitulo_sel])
        if subcaps_disponibles:
            subcap_labels = ["(Todos los subcapítulos)"] + subcaps_disponibles
            subcap_idx = st.selectbox(
                "Subcapítulo",
                options=range(len(subcap_labels)),
                format_func=lambda i: subcap_labels[i],
                key=f"{key_prefix}_subcap_{v}",
                label_visibility="collapsed",
            )
            if subcap_idx > 0:
                subcapitulo_sel = subcap_labels[subcap_idx]

    st.divider()

    # ── Relevancia ────────────────────────────────────────────────────────────
    st.markdown("#### ⭐ Relevancia PY")

    relevancia_sel = st.multiselect(
        "Relevancia",
        options=_RELEVANCIA_OPTS,
        default=_RELEVANCIA_OPTS,          # todas activas por defecto
        key=f"{key_prefix}_rel_{v}",
        format_func=lambda r: _RELEVANCIA_LABELS.get(r, r),
        label_visibility="collapsed",
    )

    st.divider()

    # ── Tipo de ítem ──────────────────────────────────────────────────────────
    st.markdown("#### 🏷 Tipo de ítem")

    solo_servicios = st.toggle(
        "Solo servicios (SER.CG)",
        value=True,
        key=f"{key_prefix}_solo_svc_{v}",
        help="Desactivar para ver también MAT., M.O., EQ.AQ. y otros",
    )
    clases_sel: list[str] = []
    if not solo_servicios:
        clases_sel = st.multiselect(
            "Clases a incluir",
            options=_CLASE_OPTS,
            default=_CLASE_OPTS,
            key=f"{key_prefix}_clases_{v}",
            label_visibility="collapsed",
        )

    st.divider()

    # ── Otros ─────────────────────────────────────────────────────────────────
    st.markdown("#### ⚙ Otros")

    solo_traducidos = st.toggle(
        "Solo ítems con traducción ES",
        value=False,
        key=f"{key_prefix}_trad_{v}",
    )

    n_rev = get_count_revision()
    rev_label = f"🔬 Solo en revisión ({n_rev})" if n_rev else "🔬 Solo en revisión"
    solo_revision = st.toggle(
        rev_label,
        value=False,
        key=f"{key_prefix}_rev_{v}",
    )

    # ── Contador de filtros activos + botón Limpiar ───────────────────────────
    st.divider()

    n_activos = sum([
        bool(busqueda),
        capitulo_sel is not None,
        subcapitulo_sel is not None,
        set(relevancia_sel) != set(_RELEVANCIA_OPTS),
        not solo_servicios,
        solo_traducidos,
        solo_revision,
    ])

    col_info, col_btn = st.columns([3, 2])
    with col_info:
        if n_activos:
            st.caption(f"🔵 {n_activos} filtro{'s' if n_activos > 1 else ''} activo{'s' if n_activos > 1 else ''}")
        else:
            st.caption("Sin filtros activos")
    with col_btn:
        if st.button(
            "🗑 Limpiar",
            key=f"{key_prefix}_clear",
            use_container_width=True,
            disabled=(n_activos == 0),
        ):
            st.session_state[vk] += 1
            st.rerun()

    # ── Armar dict de filtros ─────────────────────────────────────────────────
    modo_map = {"Descripción": "descripcion", "Código": "codigo", "Ambos": "ambos"}

    return {
        "busqueda":        busqueda or None,
        "busqueda_modo":   modo_map[modo_busqueda],
        "capitulos":       [capitulo_sel] if capitulo_sel else None,
        "subcapitulos":    [subcapitulo_sel] if subcapitulo_sel else None,
        "relevancia":      relevancia_sel or None,
        "clases":          clases_sel or None,
        "solo_servicios":  solo_servicios,
        "solo_traducidos": solo_traducidos,
        "solo_revision":   solo_revision,
    }
