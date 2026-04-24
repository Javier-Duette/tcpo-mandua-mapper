"""selector_mandua.py — Modal para asignar precio Mandu'a a un favorito."""
import streamlit as st

from app.utils.formatters import fmt_gs
from app.utils.queries import actualizar_favorito, buscar_mandua


@st.dialog("Asignar precio Mandu'a", width="large")
def modal_selector_mandua(fav_id: int, fav_desc: str = "") -> None:
    """
    Dialog que permite buscar en Mandu'a y asignar precio a un favorito.
    Cierra al confirmar (via st.rerun).
    """
    if fav_desc:
        st.caption(f"Partida: **{fav_desc[:80]}**")

    tipo = st.radio(
        "Tipo de precio",
        options=["material", "mano_obra", "manual"],
        format_func=lambda t: {
            "material":  "📦 Material (Mandu'a)",
            "mano_obra": "👷 Mano de obra (Mandu'a)",
            "manual":    "✏️ Precio manual",
        }[t],
        horizontal=True,
        key=f"tipo_modal_{fav_id}",
    )

    if tipo == "manual":
        precio_manual = st.number_input(
            "Precio unitario (Gs.)",
            min_value=0,
            step=1000,
            key=f"precio_manual_{fav_id}",
        )
        st.caption(f"= {fmt_gs(precio_manual)}")
        if st.button("✅ Confirmar precio manual", use_container_width=True,
                     key=f"conf_manual_{fav_id}"):
            actualizar_favorito(fav_id, {
                "mandua_tipo":               None,
                "mandua_id":                 None,
                "precio_unitario_manual_gs": precio_manual,
            })
            st.toast("Precio manual guardado", icon="✅")
            st.rerun()
        return

    # búsqueda en Mandu'a
    q = st.text_input(
        "🔍 Buscar en Mandu'a",
        placeholder="ej: cemento, hierro, oficial albañil…",
        key=f"busq_mandua_{fav_id}",
    )

    if not q:
        st.info("Escribí al menos 2 caracteres para buscar.")
        return

    df = buscar_mandua(tipo, q)
    if df.empty:
        st.warning("Sin resultados. Probá con otro término.")
        return

    st.dataframe(
        df[["id", "descripcion", "unidad", "precio_gs"]].rename(columns={
            "id":          "ID",
            "descripcion": "Descripción",
            "unidad":      "Unidad",
            "precio_gs":   "Precio Gs.",
        }),
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key=f"tabla_mandua_{fav_id}",
    )

    event = st.session_state.get(f"tabla_mandua_{fav_id}")
    sel_rows = event.selection.get("rows", []) if event and hasattr(event, "selection") else []

    if sel_rows:
        idx      = sel_rows[0]
        mandua_row = df.iloc[idx]
        precio   = mandua_row.get("precio_gs")

        st.success(
            f"Seleccionado: **{mandua_row['descripcion']}**  ·  {fmt_gs(precio)}"
        )

        # permitir ajuste del precio
        precio_adj = st.number_input(
            "Ajustar precio (Gs.) — editable",
            value=int(precio) if precio else 0,
            step=1000,
            key=f"precio_adj_{fav_id}",
        )

        if st.button("✅ Confirmar selección", use_container_width=True,
                     key=f"conf_sel_{fav_id}"):
            actualizar_favorito(fav_id, {
                "mandua_tipo":               tipo,
                "mandua_id":                 int(mandua_row["id"]),
                "precio_unitario_manual_gs": precio_adj,
            })
            st.toast(f"Precio asignado: {fmt_gs(precio_adj)}", icon="✅")
            st.rerun()
