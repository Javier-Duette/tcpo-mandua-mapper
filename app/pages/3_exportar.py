"""3_exportar.py — Exportación a Excel / CSV."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import streamlit as st

from app.utils.export import generar_csv, generar_excel_completo, generar_excel_dynamo
from app.utils.formatters import fmt_gs
from app.utils.queries import get_favoritos_con_detalle, get_proyectos

st.set_page_config(page_title="Exportar — TCPO PY", layout="wide",
                   page_icon="📤", initial_sidebar_state="collapsed")

if "proyecto_activo_id" not in st.session_state:
    st.session_state.proyecto_activo_id = None

st.title("📤 Exportar proyecto")

# ---------------------------------------------------------------------------
# Selector de proyecto
# ---------------------------------------------------------------------------
df_proy = get_proyectos()
if df_proy.empty:
    st.warning("No hay proyectos. Creá uno en la página Proyectos.")
    st.stop()

proy_opts = {row["nombre"]: row["id"] for _, row in df_proy.iterrows()}
default   = st.session_state.get("proyecto_activo_nombre")
idx       = list(proy_opts.keys()).index(default) if default in proy_opts else 0

sel_nombre = st.selectbox("Proyecto a exportar", options=list(proy_opts.keys()), index=idx)
sel_id     = proy_opts[sel_nombre]

df_favs = get_favoritos_con_detalle(sel_id)
if df_favs.empty:
    st.info(f"El proyecto «{sel_nombre}» no tiene favoritos todavía.")
    st.stop()

# ---------------------------------------------------------------------------
# Opciones de exportación
# ---------------------------------------------------------------------------
st.divider()
col_opt, col_prev = st.columns([1, 2])

with col_opt:
    st.subheader("⚙️ Opciones")

    formato = st.radio(
        "Formato",
        options=["Excel completo", "Excel Dynamo-friendly", "CSV"],
        key="exp_formato",
    )
    idioma = st.radio(
        "Idioma de descripciones",
        options=["ES", "PT", "ambos"],
        horizontal=True,
        key="exp_idioma",
    )

    total_gs  = (
        df_favs["cantidad_estimada"].fillna(0) *
        df_favs["precio_unitario_manual_gs"].fillna(0)
    ).sum()
    sin_precio = (
        df_favs["precio_unitario_manual_gs"].isna() |
        (df_favs["precio_unitario_manual_gs"] == 0)
    ).sum()

    st.metric("Total estimado",    fmt_gs(total_gs))
    st.metric("Partidas sin precio", sin_precio)
    if sin_precio > 0:
        st.warning(f"{sin_precio} partidas no tienen precio asignado — "
                   "aparecerán con subtotal 0.")

# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------
with col_prev:
    st.subheader("👁️ Vista previa")
    preview_cols = ["codigo", "descripcion_es", "unidad",
                    "cantidad_estimada", "precio_unitario_manual_gs", "match_mandua"]
    cols_ok = [c for c in preview_cols if c in df_favs.columns]
    st.dataframe(
        df_favs[cols_ok].rename(columns={
            "codigo":                    "Código",
            "descripcion_es":            "Descripción ES",
            "unidad":                    "Unidad",
            "cantidad_estimada":         "Cantidad",
            "precio_unitario_manual_gs": "Precio Gs.",
            "match_mandua":              "Match Mandu'a",
        }),
        use_container_width=True,
        hide_index=True,
        height=350,
    )

# ---------------------------------------------------------------------------
# Botón de descarga
# ---------------------------------------------------------------------------
st.divider()
ts   = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M")
safe = sel_nombre.replace(" ", "_").replace("/", "-")[:30]

if formato == "Excel completo":
    data      = generar_excel_completo(df_favs, sel_nombre, idioma)
    filename  = f"TCPO_{safe}_{ts}.xlsx"
    mime      = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
elif formato == "Excel Dynamo-friendly":
    data      = generar_excel_dynamo(df_favs, sel_nombre, idioma)
    filename  = f"TCPO_Dynamo_{safe}_{ts}.xlsx"
    mime      = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
else:
    data      = generar_csv(df_favs, idioma).encode("utf-8")
    filename  = f"TCPO_{safe}_{ts}.csv"
    mime      = "text/csv"

st.download_button(
    label     = f"⬇️ Descargar {formato}",
    data      = data,
    file_name = filename,
    mime      = mime,
    type      = "primary",
    use_container_width = True,
)
