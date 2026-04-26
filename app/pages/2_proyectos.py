"""2_proyectos.py — Gestión de proyectos y favoritos."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from app.components.selector_mandua import modal_selector_mandua
from app.utils.formatters import fmt_gs, relevancia_badge
from app.utils.queries import (
    actualizar_favorito, crear_proyecto, eliminar_favorito,
    eliminar_proyecto, get_favoritos_con_detalle, get_proyectos,
    reordenar_favoritos, actualizar_proyecto,
)

st.set_page_config(page_title="Proyectos — TCPO PY", layout="wide",
                   page_icon="📋", initial_sidebar_state="collapsed")

if "proyecto_activo_id"     not in st.session_state:
    st.session_state.proyecto_activo_id     = None
if "proyecto_activo_nombre" not in st.session_state:
    st.session_state.proyecto_activo_nombre = None

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _total_proyecto(df: pd.DataFrame) -> float:
    sub = df["precio_unitario_manual_gs"].fillna(0) * df["cantidad_estimada"].fillna(0)
    return sub.sum()


def _pct_completo(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    con_precio = (df["precio_unitario_manual_gs"].notna() &
                  (df["precio_unitario_manual_gs"] > 0)).sum()
    return round(100 * con_precio / len(df))


# ---------------------------------------------------------------------------
# Sidebar — lista de proyectos + nuevo
# ---------------------------------------------------------------------------
st.title("📋 Proyectos")

col_sidebar, col_main = st.columns([1, 3])

with col_sidebar:
    st.subheader("Mis proyectos")

    df_proy = get_proyectos()
    if not df_proy.empty:
        opciones = {row["nombre"]: row["id"] for _, row in df_proy.iterrows()}
        # respetar proyecto activo
        default_nombre = st.session_state.get("proyecto_activo_nombre")
        default_idx    = (list(opciones.keys()).index(default_nombre)
                          if default_nombre in opciones else 0)
        sel_nombre = st.radio(
            "Seleccioná un proyecto",
            options=list(opciones.keys()),
            index=default_idx,
            key="proy_radio",
            label_visibility="collapsed",
        )
        sel_id = opciones[sel_nombre]
        st.session_state.proyecto_activo_id     = sel_id
        st.session_state.proyecto_activo_nombre = sel_nombre
    else:
        sel_id     = None
        sel_nombre = None
        st.info("Sin proyectos aún.")

    st.divider()

    # Crear nuevo proyecto
    with st.expander("➕ Nuevo proyecto"):
        nuevo_nombre = st.text_input("Nombre", key="nuevo_nombre")
        nuevo_desc   = st.text_area("Descripción (opcional)", key="nuevo_desc", height=60)
        if st.button("Crear", key="btn_crear_proy", type="primary"):
            if nuevo_nombre.strip():
                nuevo_id = crear_proyecto(nuevo_nombre.strip(), nuevo_desc.strip())
                st.session_state.proyecto_activo_id     = nuevo_id
                st.session_state.proyecto_activo_nombre = nuevo_nombre.strip()
                st.toast(f"Proyecto «{nuevo_nombre}» creado", icon="✅")
                st.rerun()
            else:
                st.error("El nombre no puede estar vacío.")

# ---------------------------------------------------------------------------
# Contenido principal — favoritos del proyecto seleccionado
# ---------------------------------------------------------------------------
with col_main:
    if not sel_id:
        st.info("Creá o seleccioná un proyecto en el panel izquierdo.")
        st.stop()

    df_favs = get_favoritos_con_detalle(sel_id)

    # Header del proyecto
    hcol1, hcol2, hcol3 = st.columns([3, 1, 1])
    with hcol1:
        st.subheader(f"📁 {sel_nombre}")
    with hcol2:
        if st.button("✏️ Editar", key="btn_edit_proy"):
            st.session_state[f"edit_proy_{sel_id}"] = True
    with hcol3:
        if st.button("🗑️ Eliminar proyecto", key="btn_del_proy"):
            st.session_state[f"confirm_del_proy_{sel_id}"] = True

    # Confirmación eliminar proyecto
    if st.session_state.get(f"confirm_del_proy_{sel_id}"):
        st.warning(f"¿Confirmar eliminación de «{sel_nombre}»? Se perderán todos los favoritos.")
        c1, c2 = st.columns(2)
        if c1.button("✅ Sí, eliminar", key="conf_del_si"):
            eliminar_proyecto(sel_id)
            st.session_state.proyecto_activo_id     = None
            st.session_state.proyecto_activo_nombre = None
            st.session_state.pop(f"confirm_del_proy_{sel_id}", None)
            st.toast("Proyecto eliminado", icon="🗑️")
            st.rerun()
        if c2.button("❌ Cancelar", key="conf_del_no"):
            st.session_state.pop(f"confirm_del_proy_{sel_id}", None)
            st.rerun()

    # Editar proyecto
    if st.session_state.get(f"edit_proy_{sel_id}"):
        with st.form(key=f"form_edit_{sel_id}"):
            new_nom  = st.text_input("Nombre", value=sel_nombre)
            proy_row = df_proy[df_proy["id"] == sel_id].iloc[0] if not df_proy.empty else {}
            new_desc = st.text_area("Descripción", value=proy_row.get("descripcion", "") or "")
            if st.form_submit_button("Guardar"):
                actualizar_proyecto(sel_id, new_nom.strip(), new_desc.strip())
                st.session_state.pop(f"edit_proy_{sel_id}", None)
                st.toast("Proyecto actualizado", icon="✅")
                st.rerun()

    # Métricas del proyecto
    total_gs  = _total_proyecto(df_favs)
    pct       = _pct_completo(df_favs)
    sin_precio = (df_favs["precio_unitario_manual_gs"].isna() |
                  (df_favs["precio_unitario_manual_gs"] == 0)).sum() if not df_favs.empty else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Partidas",         len(df_favs))
    m2.metric("Total estimado",   fmt_gs(total_gs))
    m3.metric("Sin precio",       sin_precio)
    m4.metric("Completitud",      f"{pct}%")

    st.divider()

    if df_favs.empty:
        st.info("Este proyecto no tiene favoritos todavía. "
                "Buscalos en el **Explorador** y agregarlos con ⭐.")
        st.stop()

    # ---------------------------------------------------------------------------
    # Tabla editable de favoritos
    # ---------------------------------------------------------------------------
    st.markdown("#### Partidas del proyecto")

    df_ser   = df_favs[df_favs["class"].str.startswith("SER.", na=False)].copy()
    df_otros = df_favs[~df_favs["class"].str.startswith("SER.", na=False)].copy()

    # --- Servicios SER.CG: precio calculado automáticamente desde TCPO ---
    if not df_ser.empty:
        st.caption("🔧 **Servicios** — precio calculado desde composición TCPO. "
                   "Para modificarlos → ⚙️ Configuración → Precios TCPO")

        df_ser["precio_efectivo"] = df_ser["precio_gs"].fillna(0)
        df_ser["subtotal"]        = df_ser["cantidad_estimada"].fillna(0) * df_ser["precio_efectivo"]
        df_ser["relevancia_py"]   = df_ser["relevancia_py"].fillna("sin_clasificar")

        disp_ser = df_ser[[
            "fav_id", "orden", "codigo", "descripcion_es", "unidad",
            "cantidad_estimada", "precio_efectivo", "subtotal",
            "match_mandua", "relevancia_py", "notas_propias",
        ]].copy()

        edited_ser = st.data_editor(
            disp_ser.drop(columns=["fav_id"]),
            column_config={
                "orden":           st.column_config.NumberColumn("Orden",        disabled=True),
                "codigo":          st.column_config.TextColumn("Código",         disabled=True),
                "descripcion_es":  st.column_config.TextColumn("Descripción",    disabled=True, width="large"),
                "unidad":          st.column_config.TextColumn("Unidad",         disabled=True),
                "cantidad_estimada": st.column_config.NumberColumn("Cantidad",   min_value=0, step=0.01),
                "precio_efectivo": st.column_config.NumberColumn("Precio Gs.",   disabled=True, format="%d",
                                                                  help="Calculado automáticamente desde TCPO"),
                "subtotal":        st.column_config.NumberColumn("Subtotal Gs.", disabled=True, format="%d"),
                "match_mandua":    st.column_config.TextColumn("Match Mandu'a",  disabled=True),
                "relevancia_py":   st.column_config.TextColumn("Relevancia",     disabled=True),
                "notas_propias":   st.column_config.TextColumn("Notas"),
            },
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            key=f"editor_ser_{sel_id}",
        )

        if st.button("💾 Guardar cambios", key="btn_save_ser", type="primary"):
            for i, row in edited_ser.iterrows():
                fav_id = int(disp_ser.iloc[i]["fav_id"])
                actualizar_favorito(fav_id, {
                    "cantidad_estimada": row.get("cantidad_estimada"),
                    "notas_propias":     row.get("notas_propias") or None,
                })
            st.toast("Cambios guardados", icon="💾")
            st.rerun()

    # --- Otros insumos (MAT., M.O., etc.): precio manual ---
    if not df_otros.empty:
        st.caption("📦 **Insumos directos** — precio editable manualmente")

        df_otros["subtotal"]      = (df_otros["cantidad_estimada"].fillna(0) *
                                     df_otros["precio_unitario_manual_gs"].fillna(0))
        df_otros["relevancia_py"] = df_otros["relevancia_py"].fillna("sin_clasificar")

        disp_otros = df_otros[[
            "fav_id", "orden", "codigo", "descripcion_es", "unidad",
            "cantidad_estimada", "precio_unitario_manual_gs", "subtotal",
            "match_mandua", "relevancia_py", "notas_propias",
        ]].copy()

        edited_otros = st.data_editor(
            disp_otros.drop(columns=["fav_id"]),
            column_config={
                "orden":                     st.column_config.NumberColumn("Orden",        disabled=True),
                "codigo":                    st.column_config.TextColumn("Código",         disabled=True),
                "descripcion_es":            st.column_config.TextColumn("Descripción",    disabled=True, width="large"),
                "unidad":                    st.column_config.TextColumn("Unidad",         disabled=True),
                "cantidad_estimada":         st.column_config.NumberColumn("Cantidad",     min_value=0, step=0.01),
                "precio_unitario_manual_gs": st.column_config.NumberColumn("Precio Gs.",   min_value=0, step=100, format="%d"),
                "subtotal":                  st.column_config.NumberColumn("Subtotal Gs.", disabled=True, format="%d"),
                "match_mandua":              st.column_config.TextColumn("Match Mandu'a",  disabled=True),
                "relevancia_py":             st.column_config.TextColumn("Relevancia",     disabled=True),
                "notas_propias":             st.column_config.TextColumn("Notas"),
            },
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            key=f"editor_otros_{sel_id}",
        )

        if st.button("💾 Guardar cambios", key="btn_save_otros", type="primary"):
            for i, row in edited_otros.iterrows():
                fav_id = int(disp_otros.iloc[i]["fav_id"])
                actualizar_favorito(fav_id, {
                    "cantidad_estimada":         row.get("cantidad_estimada"),
                    "precio_unitario_manual_gs": row.get("precio_unitario_manual_gs"),
                    "notas_propias":             row.get("notas_propias") or None,
                })
            st.toast("Cambios guardados", icon="💾")
            st.rerun()

    st.divider()

    # ---------------------------------------------------------------------------
    # Acciones por fila: asignar Mandu'a, eliminar
    # ---------------------------------------------------------------------------
    st.markdown("#### Acciones por partida")
    for _, row in df_favs.iterrows():
        fav_id   = int(row["fav_id"])
        desc     = str(row.get("descripcion_es") or row.get("descripcion_pt") or "")[:60]
        precio   = row.get("precio_unitario_manual_gs")
        match    = row.get("match_mandua") or "—"

        ca, cb, cc = st.columns([4, 2, 1])
        ca.markdown(f"**{row.get('codigo','')}** — {desc}")
        with cb:
            if st.button(
                f"💲 {'Cambiar' if precio else 'Asignar'} precio Mandu'a",
                key=f"btn_mandua_{fav_id}",
            ):
                modal_selector_mandua(fav_id, desc)
        with cc:
            if st.button("🗑️", key=f"btn_del_{fav_id}",
                         help="Eliminar del proyecto"):
                if st.session_state.get(f"confirm_del_fav_{fav_id}"):
                    eliminar_favorito(fav_id)
                    st.session_state.pop(f"confirm_del_fav_{fav_id}", None)
                    st.toast("Eliminado del proyecto", icon="🗑️")
                    st.rerun()
                else:
                    st.session_state[f"confirm_del_fav_{fav_id}"] = True
                    st.rerun()

        if st.session_state.get(f"confirm_del_fav_{fav_id}"):
            st.warning(f"¿Eliminar «{desc[:40]}» del proyecto?")
            dc1, dc2 = st.columns(2)
            if dc1.button("Sí", key=f"del_yes_{fav_id}"):
                eliminar_favorito(fav_id)
                st.session_state.pop(f"confirm_del_fav_{fav_id}", None)
                st.toast("Eliminado", icon="🗑️")
                st.rerun()
            if dc2.button("No", key=f"del_no_{fav_id}"):
                st.session_state.pop(f"confirm_del_fav_{fav_id}", None)
                st.rerun()

    # ---------------------------------------------------------------------------
    # Reordenar con botones ↑↓
    # ---------------------------------------------------------------------------
    st.divider()
    st.markdown("#### Reordenar partidas")
    fav_ids = list(df_favs["fav_id"].astype(int))
    for i, fid in enumerate(fav_ids):
        desc = str(df_favs.iloc[i].get("descripcion_es") or "")[:40]
        rc1, rc2, rc3 = st.columns([4, 1, 1])
        rc1.caption(f"{i+1}. {desc}")
        if rc2.button("↑", key=f"up_{fid}", disabled=(i == 0)):
            fav_ids[i], fav_ids[i - 1] = fav_ids[i - 1], fav_ids[i]
            reordenar_favoritos(fav_ids)
            st.rerun()
        if rc3.button("↓", key=f"dn_{fid}", disabled=(i == len(fav_ids) - 1)):
            fav_ids[i], fav_ids[i + 1] = fav_ids[i + 1], fav_ids[i]
            reordenar_favoritos(fav_ids)
            st.rerun()
