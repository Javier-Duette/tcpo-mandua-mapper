"""1_explorador.py — Navegación y búsqueda del catálogo TCPO."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import streamlit as st

from app.components.detalle_partida import panel_detalle
from app.components.filtros import panel_filtros
from app.components.tabla_partidas import mostrar_tabla

st.set_page_config(page_title="Explorador — TCPO PY", layout="wide",
                   page_icon="🔍", initial_sidebar_state="collapsed")

# Heredar estado de sesión
for key, default in [
    ("proyecto_activo_id",     None),
    ("proyecto_activo_nombre", None),
    ("selected_item_id",       None),
    ("tabla_page",             0),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("🔍 Explorador de partidas TCPO")

proyecto_id     = st.session_state.proyecto_activo_id
proyecto_nombre = st.session_state.proyecto_activo_nombre
if proyecto_nombre:
    st.caption(f"Proyecto activo: **{proyecto_nombre}**")
else:
    st.caption("Sin proyecto activo — seleccioná uno en el **Dashboard** o en **Proyectos**.")

# ---------------------------------------------------------------------------
# Layout: filtros | tabla | detalle
# ---------------------------------------------------------------------------
col_izq, col_centro, col_der = st.columns([2.5, 5, 2.5])

# === COLUMNA IZQUIERDA — Filtros (incluye búsqueda) ===
with col_izq:
    filtros = panel_filtros(key_prefix="exp")

# === COLUMNA CENTRAL — Tabla ===
with col_centro:
    # Reset paginación al cambiar filtros
    filtros_key = str(sorted(
        {k: str(v) for k, v in filtros.items() if v is not None}.items()
    ))
    if st.session_state.get("_last_filtros_key") != filtros_key:
        st.session_state.tabla_page        = 0
        st.session_state._last_filtros_key = filtros_key

    selected_id = mostrar_tabla(filtros, proyecto_id=proyecto_id)
    if selected_id:
        st.session_state.selected_item_id = selected_id

# === COLUMNA DERECHA — Detalle ===
with col_der:
    item_id = st.session_state.get("selected_item_id")
    if item_id:
        panel_detalle(item_id, proyecto_id=proyecto_id)
    else:
        st.info("👈 Hacé click en una fila para ver el detalle.")
