"""detalle_partida.py — Panel de detalle de una partida TCPO."""
import streamlit as st

from app.utils.formatters import (
    clase_label, fmt_brl, fmt_coef, fmt_gs, relevancia_badge, relevancia_color,
)
from app.utils.queries import (
    agregar_favorito, esta_en_favoritos, get_detalle_partida,
    get_insumos_de_partida, get_nota_partida, guardar_nota_partida,
    get_proyectos,
)


def panel_detalle(tcpo_item_id: int, proyecto_id: int | None = None) -> None:
    """Renderiza el panel de detalle para un tcpo_item_id dado."""
    item = get_detalle_partida(tcpo_item_id)
    if not item:
        st.info("Seleccioná una partida para ver el detalle.")
        return

    rel   = item.get("relevancia_py") or "sin_clasificar"
    color = relevancia_color(rel)
    clase = item.get("class") or ""

    # --- encabezado ---
    st.markdown(
        f"<div style='border-left:4px solid {color}; padding:6px 10px; "
        f"background:rgba(0,0,0,0.04); border-radius:4px; margin-bottom:8px'>"
        f"<b>{item.get('codigo','')}</b> &nbsp;·&nbsp; "
        f"<span style='color:{color}'>{relevancia_badge(rel)}</span> &nbsp;·&nbsp; "
        f"{clase_label(clase)}"
        f"</div>",
        unsafe_allow_html=True,
    )

    # --- descripción ES (destacada) ---
    desc_es = item.get("descripcion_es") or ""
    if desc_es:
        st.markdown(f"**{desc_es}**")
    else:
        st.caption("*(sin traducción)*")

    # --- justificación relevancia ---
    just = item.get("relevancia_justificacion") or ""
    if just:
        st.caption(f"_{just}_")

    # --- descripción PT (colapsable) ---
    desc_pt = item.get("descripcion_pt") or ""
    if desc_pt:
        with st.expander("Descripción PT original"):
            st.text(desc_pt)

    st.divider()

    # --- datos técnicos ---
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Unidad",      item.get("unidad") or "—")
        st.metric("Coeficiente", fmt_coef(item.get("coef")))
    with c2:
        precio_brl = item.get("precio_brl")
        if rel == "no_aplica":
            st.markdown(f"~~{fmt_brl(precio_brl)}~~ *(no aplica PY)*")
        else:
            st.metric("Precio ref. BRL", fmt_brl(precio_brl))
        st.metric("Total BRL", fmt_brl(item.get("precio_total_brl")))

    # --- capítulo / subcapítulo ---
    cap    = item.get("capitulo") or ""
    subcap = item.get("subcapitulo") or ""
    if cap:
        st.caption(f"📁 {cap}")
    if subcap:
        st.caption(f"   └ {subcap}")

    # --- insumos (solo para SER.CG) ---
    if clase == "SER.CG":
        df_ins = get_insumos_de_partida(tcpo_item_id)
        if not df_ins.empty:
            with st.expander(f"Desglose de insumos ({len(df_ins)} items)"):
                cols_show = ["class", "descripcion_es", "unidad", "coef", "precio_total_brl"]
                cols_ok   = [c for c in cols_show if c in df_ins.columns]
                rename    = {
                    "class":             "Clase",
                    "descripcion_es":    "Descripción ES",
                    "unidad":            "Unidad",
                    "coef":              "Coef.",
                    "precio_total_brl":  "Total BRL",
                }
                st.dataframe(
                    df_ins[cols_ok].rename(columns=rename),
                    use_container_width=True,
                    hide_index=True,
                )

    st.divider()

    # --- notas personales ---
    nota_actual = get_nota_partida(tcpo_item_id)
    nota_nueva  = st.text_area(
        "📝 Notas personales",
        value=nota_actual,
        key=f"nota_{tcpo_item_id}",
        height=80,
        placeholder="Agregar nota sobre esta partida…",
    )
    if nota_nueva != nota_actual:
        guardar_nota_partida(tcpo_item_id, nota_nueva)
        st.toast("Nota guardada", icon="📝")

    # --- agregar a proyecto ---
    st.divider()
    df_proyectos = get_proyectos()
    if df_proyectos.empty:
        st.caption("No hay proyectos. Creá uno en la página Proyectos.")
    else:
        proy_opts = {row["nombre"]: row["id"] for _, row in df_proyectos.iterrows()}
        # mostrar proyecto activo por defecto
        default_idx = 0
        if proyecto_id:
            nombres = list(proy_opts.keys())
            ids     = list(proy_opts.values())
            if proyecto_id in ids:
                default_idx = ids.index(proyecto_id)

        sel_nombre = st.selectbox(
            "Agregar al proyecto",
            options=list(proy_opts.keys()),
            index=default_idx,
            key=f"sel_proy_{tcpo_item_id}",
        )
        sel_proy_id = proy_opts[sel_nombre]
        ya_fav      = esta_en_favoritos(sel_proy_id, tcpo_item_id)

        if ya_fav:
            st.success("⭐ Ya es favorito en este proyecto")
        else:
            if st.button("⭐ Agregar a favoritos", key=f"add_fav_{tcpo_item_id}",
                         use_container_width=True):
                agregar_favorito(sel_proy_id, tcpo_item_id)
                st.toast(f"Agregado a «{sel_nombre}»", icon="⭐")
                st.rerun()
