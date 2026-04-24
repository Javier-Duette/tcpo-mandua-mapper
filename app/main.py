"""main.py — Home / Dashboard de TCPO Explorer PY."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import streamlit as st
import pandas as pd

from app.utils.queries import get_dashboard_stats, get_proyectos
from app.utils.formatters import relevancia_badge

# ---------------------------------------------------------------------------
# Configuración de página (solo en main.py)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="TCPO Explorer PY",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "TCPO Explorer PY — tcpo-mandua-mapper v0.1"},
)

# Inicializar session_state global
if "proyecto_activo_id"   not in st.session_state:
    st.session_state.proyecto_activo_id   = None
if "proyecto_activo_nombre" not in st.session_state:
    st.session_state.proyecto_activo_nombre = None
if "selected_item_id" not in st.session_state:
    st.session_state.selected_item_id = None

# ---------------------------------------------------------------------------
# Sidebar — selector de proyecto activo
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🏗️ TCPO Explorer PY")
    st.divider()

    df_proy = get_proyectos()
    if not df_proy.empty:
        proy_opts = {"(ninguno)": None} | {
            row["nombre"]: row["id"] for _, row in df_proy.iterrows()
        }
        sel = st.selectbox(
            "Proyecto activo",
            options=list(proy_opts.keys()),
            key="sb_proyecto_activo",
        )
        st.session_state.proyecto_activo_id     = proy_opts[sel]
        st.session_state.proyecto_activo_nombre = sel if sel != "(ninguno)" else None
    else:
        st.caption("Sin proyectos. Creá uno en **Proyectos**.")

    st.divider()
    st.caption("v0.1 — tcpo-mandua-mapper")

# ---------------------------------------------------------------------------
# Dashboard principal
# ---------------------------------------------------------------------------
st.title("🏗️ TCPO Explorer PY")
st.caption("Catálogo TCPO v15 adaptado para presupuestos de obra en Paraguay")

stats = get_dashboard_stats()

# Fila de métricas
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Partidas traducidas",  f"{stats['traducidos']:,}",
          f"{stats['pct_trad']}% del total")
m2.metric("🟢 Alta relevancia",   f"{stats['dist_rel'].get('alta', 0):,}")
m3.metric("🟡 Media relevancia",  f"{stats['dist_rel'].get('media', 0):,}")
m4.metric("Proyectos activos",    stats["n_proyectos"])
m5.metric("Favoritos totales",    stats["n_favoritos"])

st.divider()

# Dos columnas: gráfico relevancia + tabla cobertura capítulos
col_graf, col_tabla = st.columns([1, 1])

with col_graf:
    st.subheader("Distribución por relevancia")
    rel_data = {
        k: v for k, v in stats["dist_rel"].items()
        if k not in (None, "sin_clasificar")
    }
    if rel_data:
        df_rel = pd.DataFrame.from_dict(
            rel_data, orient="index", columns=["Partidas"]
        )
        df_rel.index.name = "Relevancia"
        st.bar_chart(df_rel, color="#1f77b4")

with col_tabla:
    st.subheader("Proyectos activos")
    if df_proy.empty:
        st.info("No hay proyectos. Creá el primero en la página **Proyectos**.")
    else:
        st.dataframe(
            df_proy[["nombre", "n_favoritos", "fecha_creacion"]].rename(columns={
                "nombre":         "Proyecto",
                "n_favoritos":    "Favoritos",
                "fecha_creacion": "Creado",
            }),
            use_container_width=True,
            hide_index=True,
        )

st.divider()

# CTA
if st.button("🔍 Ir al Explorador de partidas", type="primary", use_container_width=False):
    st.switch_page("pages/1_explorador.py")
