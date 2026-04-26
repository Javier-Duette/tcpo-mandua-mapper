"""tabla_partidas.py — Tabla interactiva de partidas TCPO."""
import pandas as pd
import streamlit as st

from app.utils.formatters import fmt_brl
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
    Tabla paginada de partidas con selección por checkbox.
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

    # --- header: contador + paginación ---
    col_info, col_prev, col_pg, col_next = st.columns([4, 1, 2, 1])
    with col_info:
        st.caption(f"**{total:,}** partidas  |  página {page+1}/{n_pages}")
    with col_prev:
        if st.button("◀", disabled=(page == 0), key="pg_prev"):
            st.session_state.tabla_page -= 1
            st.rerun()
    with col_pg:
        new_pg = st.number_input("", min_value=1, max_value=n_pages,
                                  value=page + 1, key="pg_num",
                                  label_visibility="collapsed")
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

    # Solo mostrar columna Clase si hay mezcla de tipos
    solo_servicios = filtros.get("solo_servicios", True) and not filtros.get("clases")

    desc_col = df["descripcion_es"].fillna(df["descripcion_pt"]).fillna("")

    cols: dict = {"ID": df["id"]}
    if "es_favorito" in df.columns:
        cols["★"] = df["es_favorito"].map({1: "⭐", 0: ""})
    cols["Código"]      = df["codigo"]
    if not solo_servicios:
        cols["Clase"]   = df["class"]
    cols["Descripción"] = desc_col          # sin truncar — AG Grid muestra tooltip completo
    cols["Unidad"]      = df["unidad"].fillna("")
    cols["Relevancia"]  = df["relevancia_py"].map(_REL_BADGE).fillna("⚪")
    if "en_revision" in df.columns:
        cols["🔬"] = df["en_revision"].map({1: "🔬", 0: ""})

    display = pd.DataFrame(cols)

    # CSS: wrap de texto en columna Descripción + filas más altas
    st.markdown("""
    <style>
    div[data-testid="stDataFrame"] [col-id="Descripción"] .ag-cell-value {
        white-space: normal !important;
        word-break: break-word !important;
        line-height: 1.35 !important;
        overflow: hidden !important;
    }
    div[data-testid="stDataFrame"] .ag-row {
        height: 54px !important;
    }
    div[data-testid="stDataFrame"] .ag-header-cell-label {
        white-space: normal !important;
    }
    </style>
    """, unsafe_allow_html=True)

    col_cfg = {
        "★":           st.column_config.TextColumn("★",          width=30),
        "Código":      st.column_config.TextColumn("Código",      width="small"),
        "Clase":       st.column_config.TextColumn("Clase",       width=70),
        "Descripción": st.column_config.TextColumn("Descripción", width="large"),
        "Unidad":      st.column_config.TextColumn("Unidad",      width=60),
        "Relevancia":  st.column_config.TextColumn("Relevancia",  width=110),
        "🔬":          st.column_config.TextColumn("🔬",          width=36),
    }

    ROW_H = 56   # debe coincidir con el CSS de arriba
    event = st.dataframe(
        display.drop(columns=["ID"]),
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config=col_cfg,
        height=min(ROW_H * len(display) + 38, 700),
        key="tabla_principal",
    )

    selected_id: int | None = None
    sel_rows = event.selection.get("rows", []) if event else []
    if sel_rows:
        idx = sel_rows[0]
        if idx < len(display):
            selected_id = int(display.iloc[idx]["ID"])
            st.session_state.selected_item_id = selected_id

    # --- descripción completa de la fila seleccionada ---
    if selected_id:
        row_sel = display[display["ID"] == selected_id].iloc[0]
        desc_full = df.loc[df["id"] == selected_id, "descripcion_es"].values
        desc_full = desc_full[0] if len(desc_full) and desc_full[0] else \
                    df.loc[df["id"] == selected_id, "descripcion_pt"].values[0]
        st.markdown(
            f"<div style='background:#1e2a3a;padding:6px 12px;border-radius:6px;"
            f"border-left:3px solid #4a9eff;font-size:0.85em;color:#cdd9e5;"
            f"margin-bottom:4px'>"
            f"<b style='color:#7ab3ff'>{row_sel['Código']}</b>&nbsp;&nbsp;{desc_full}"
            f"</div>",
            unsafe_allow_html=True,
        )

    # --- acción rápida favorito ---
    if selected_id and proyecto_id:
        ya_fav    = esta_en_favoritos(proyecto_id, selected_id)
        btn_label = "➖ Quitar de favoritos" if ya_fav else "⭐ Agregar a favoritos"
        if st.button(btn_label, key=f"fav_quick_{selected_id}"):
            if ya_fav:
                from app.utils.queries import get_conn
                conn = get_conn()
                row  = conn.execute(
                    "SELECT id FROM favoritos WHERE proyecto_id=? AND tcpo_item_id=?",
                    (proyecto_id, selected_id),
                ).fetchone()
                if row:
                    eliminar_favorito(row["id"])
            else:
                agregar_favorito(proyecto_id, selected_id)
            st.toast("Favorito actualizado")
            st.rerun()

    return selected_id
