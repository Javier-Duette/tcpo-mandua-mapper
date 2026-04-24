"""tabla_partidas.py — Tabla interactiva de partidas TCPO."""
import pandas as pd
import streamlit as st

from app.utils.formatters import relevancia_badge, truncar, fmt_brl
from app.utils.queries import (
    agregar_favorito, eliminar_favorito, esta_en_favoritos, get_partidas,
    get_total_partidas,
)

PAGE_SIZE = 50

_REL_BADGE = {
    "alta":           "🟢 alta",
    "media":          "🟡 media",
    "baja":           "🟠 baja",
    "no_aplica":      "🔴 no aplica",
    "sin_clasificar": "⚪ s/c",
}


def mostrar_tabla(filtros: dict, proyecto_id: int | None = None) -> int | None:
    """
    Renderiza la tabla paginada de partidas.
    Retorna el tcpo_item_id de la fila seleccionada (o None).
    """
    # --- paginación ---
    total   = get_total_partidas(filtros)
    n_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

    if "tabla_page" not in st.session_state:
        st.session_state.tabla_page = 0
    page = st.session_state.tabla_page
    if page >= n_pages:
        page = 0
        st.session_state.tabla_page = 0

    offset = page * PAGE_SIZE
    df     = get_partidas(filtros, limit=PAGE_SIZE, offset=offset, proyecto_id=proyecto_id)

    # --- header con contador y paginación ---
    col_info, col_prev, col_pg, col_next = st.columns([4, 1, 2, 1])
    with col_info:
        st.caption(f"**{total:,}** partidas  |  página {page+1}/{n_pages}")
    with col_prev:
        if st.button("◀", disabled=(page == 0), key="pg_prev"):
            st.session_state.tabla_page -= 1
            st.rerun()
    with col_pg:
        new_pg = st.number_input("", min_value=1, max_value=n_pages,
                                  value=page + 1, key="pg_num", label_visibility="collapsed")
        if new_pg - 1 != page:
            st.session_state.tabla_page = new_pg - 1
            st.rerun()
    with col_next:
        if st.button("▶", disabled=(page >= n_pages - 1), key="pg_next"):
            st.session_state.tabla_page += 1
            st.rerun()

    if df.empty:
        st.info("No hay partidas con los filtros seleccionados.")
        return None

    # --- preparar display ---
    display = pd.DataFrame({
        "ID":          df["id"],
        "★":           df["es_favorito"].map({1: "⭐", 0: ""}) if "es_favorito" in df.columns else "",
        "Código":      df["codigo"],
        "Clase":       df["class"],
        "Descripción": df["descripcion_es"].fillna(df["descripcion_pt"]).apply(lambda s: truncar(s, 55)),
        "Unidad":      df["unidad"].fillna(""),
        "Relevancia":  df["relevancia_py"].map(_REL_BADGE).fillna("⚪"),
    })

    # --- tabla interactiva ---
    event = st.dataframe(
        display.drop(columns=["ID"]),
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="tabla_principal",
        height=min(35 * len(display) + 38, 600),
    )

    selected_id: int | None = None
    sel_rows = event.selection.get("rows", []) if event else []
    if sel_rows:
        idx = sel_rows[0]
        if idx < len(display):
            selected_id = int(display.iloc[idx]["ID"])
            st.session_state.selected_item_id = selected_id

    # --- acciones rápidas sobre item seleccionado ---
    if selected_id and proyecto_id:
        ya_fav = esta_en_favoritos(proyecto_id, selected_id)
        btn_label = "➖ Quitar de favoritos" if ya_fav else "⭐ Agregar a favoritos"
        if st.button(btn_label, key=f"fav_quick_{selected_id}"):
            if ya_fav:
                # buscar fav_id
                from app.utils.queries import get_conn
                conn  = get_conn()
                row   = conn.execute(
                    "SELECT id FROM favoritos WHERE proyecto_id=? AND tcpo_item_id=?",
                    (proyecto_id, selected_id),
                ).fetchone()
                if row:
                    eliminar_favorito(row["id"])
            else:
                agregar_favorito(proyecto_id, selected_id)
            st.toast("✅ Favorito actualizado")
            st.rerun()

    return selected_id
