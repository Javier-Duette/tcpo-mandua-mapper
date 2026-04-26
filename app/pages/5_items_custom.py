"""5_items_custom.py — Crear y gestionar ítems personalizados (PY)."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from app.utils.formatters import fmt_gs
from app.utils.queries import (
    CLASES_HOJA, CLASES_SERVICIO,
    siguiente_codigo_custom, crear_item_hoja, crear_servicio,
    listar_items_custom, eliminar_item_custom, buscar_para_componente,
    get_capitulos_distintos, recalcular_precios_cascade,
    get_detalle_partida, get_componentes_servicio_custom,
    actualizar_item_hoja_custom, actualizar_servicio_custom,
)

st.set_page_config(
    page_title="Ítems propios — TCPO PY",
    layout="wide",
    page_icon="🏗️",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Constantes locales
# ---------------------------------------------------------------------------
LABELS_HOJA = {
    "MAT.":   "Material",
    "M.O.":   "Mano de obra directa",
    "EQ.LOC": "Equipo alquilado",
    "EMPRE":  "Mano de obra empreitada",
}
LABELS_SERV = {
    "SER.CG": "Servicio completo",
    "SER.MO": "Sub-servicio",
}

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("🏗️ Mis ítems personalizados")
st.caption(
    "Creá ítems propios (con prefijo `PY`) para complementar la TCPO con productos "
    "y servicios del mercado paraguayo. No interfieren con los códigos originales."
)

tab_hoja, tab_serv, tab_lista = st.tabs([
    "➕ Nuevo ítem (material/mano de obra)",
    "➕ Nuevo servicio compuesto",
    "📋 Mis ítems",
])


# ---------------------------------------------------------------------------
# Helper: selector de capítulo (existente o libre)
# ---------------------------------------------------------------------------
def _selector_capitulo(prefix: str) -> str | None:
    """Renderiza un selector de capítulo. Retorna el capítulo elegido o None."""
    caps = ["(Sin capítulo)"] + get_capitulos_distintos() + ["+ Crear nuevo capítulo…"]
    sel  = st.selectbox("Capítulo", caps, key=f"{prefix}_cap_sel")
    if sel == "(Sin capítulo)":
        return None
    if sel == "+ Crear nuevo capítulo…":
        return st.text_input(
            "Nombre del nuevo capítulo",
            key=f"{prefix}_cap_libre",
            placeholder="Ej: 99. Ítems locales PY",
        ).strip() or None
    return sel


# ===========================================================================
# TAB 1 — Crear ítem hoja
# ===========================================================================
with tab_hoja:
    st.subheader("Material, mano de obra o equipo")
    st.caption(
        "Para ítems primarios que tienen un precio directo "
        "(no se calculan a partir de otros)."
    )

    col1, col2 = st.columns(2)
    with col1:
        clase_h = st.selectbox(
            "Tipo de ítem",
            options=list(CLASES_HOJA),
            format_func=lambda c: f"{c} — {LABELS_HOJA[c]}",
            key="h_clase",
        )
        cap_h    = _selector_capitulo("h")
        subcap_h = st.text_input("Subcapítulo (opcional)", key="h_subcap")

    with col2:
        desc_h   = st.text_area(
            "Descripción ES",
            key="h_desc",
            placeholder="Ej: Cal hidratada azul (marca local)",
            height=80,
        )
        unidad_h = st.text_input(
            "Unidad",
            key="h_unidad",
            placeholder="Ej: M2, KG, H, UN, ML…",
        )
        c_pr1, c_pr2 = st.columns([2, 3])
        with c_pr1:
            precio_h = st.number_input(
                "Precio Gs.",
                min_value=0.0, step=500.0, format="%g",
                key="h_precio",
            )
        with c_pr2:
            fuente_h = st.text_input(
                "Fuente del precio",
                key="h_fuente",
                placeholder="Ej: Mandu'a abr-2026, Cotización local",
            )

    # Vista previa del código generado
    codigo_pred_h = siguiente_codigo_custom(clase_h, cap_h)
    st.markdown(f"**Código generado:** `{codigo_pred_h}`")

    if st.button("🏗️ Crear ítem", type="primary", key="btn_crear_hoja",
                 use_container_width=False):
        try:
            new_id = crear_item_hoja(
                codigo         = codigo_pred_h,
                clase          = clase_h,
                descripcion_es = desc_h,
                unidad         = unidad_h,
                precio_gs      = precio_h,
                fuente         = fuente_h,
                capitulo       = cap_h,
                subcapitulo    = subcap_h.strip() or None,
            )
            st.success(f"✅ Ítem creado: **{codigo_pred_h}** (id={new_id})")
            st.balloons()
            # Limpiar formulario
            for k in ["h_desc", "h_unidad", "h_precio", "h_fuente", "h_subcap"]:
                st.session_state.pop(k, None)
        except ValueError as e:
            st.error(f"❌ {e}")


# ===========================================================================
# TAB 2 — Crear servicio compuesto
# ===========================================================================
with tab_serv:
    st.subheader("Servicio con composición")
    st.caption(
        "Definí el servicio y agregá sus componentes (materiales, mano de obra, "
        "otros servicios). El precio se calcula automáticamente."
    )

    # Estado de los componentes en sesión
    if "comp_list" not in st.session_state:
        st.session_state.comp_list = []

    col1, col2 = st.columns(2)
    with col1:
        clase_s = st.selectbox(
            "Tipo",
            options=list(CLASES_SERVICIO),
            format_func=lambda c: f"{c} — {LABELS_SERV[c]}",
            key="s_clase",
        )
        cap_s    = _selector_capitulo("s")
        subcap_s = st.text_input("Subcapítulo (opcional)", key="s_subcap")

    with col2:
        desc_s   = st.text_area(
            "Descripción ES",
            key="s_desc",
            placeholder="Ej: Colocación porcelanato 60×60 cm con adhesivo",
            height=80,
        )
        unidad_s = st.text_input(
            "Unidad de medida",
            key="s_unidad",
            placeholder="Ej: M2, ML, UN…",
        )

    codigo_pred_s = siguiente_codigo_custom(clase_s, cap_s)
    st.markdown(f"**Código generado:** `{codigo_pred_s}`")

    st.divider()
    st.markdown("### Composición del servicio")

    # ---- Buscador de componentes ----
    sc1, sc2 = st.columns([4, 1])
    with sc1:
        busq_comp = st.text_input(
            "🔍 Buscar componente",
            key="comp_busq",
            placeholder="Código o descripción (mín. 2 caracteres)",
        )
    with sc2:
        st.write("")
        st.write("")
        if st.button("🔄 Limpiar", key="comp_clear", use_container_width=True,
                     disabled=not st.session_state.comp_list):
            st.session_state.comp_list = []
            st.rerun()

    # Resultados de búsqueda
    if busq_comp and len(busq_comp.strip()) >= 2:
        df_res = buscar_para_componente(busq_comp.strip(), limit=20)
        if df_res.empty:
            st.info("Sin resultados.")
        else:
            with st.container(border=True):
                st.caption(f"**{len(df_res)} resultado(s)** — click ➕ para agregar")
                for _, r in df_res.iterrows():
                    rc1, rc2, rc3, rc4 = st.columns([3, 4, 2, 1])
                    rc1.markdown(f"`{r['codigo']}` · _{r['class']}_")
                    rc2.markdown(
                        f"{(r['descripcion'] or '')[:80]}"
                        f"<br><small>Unidad: <b>{r['unidad'] or '—'}</b></small>",
                        unsafe_allow_html=True,
                    )
                    rc3.markdown(f"**Gs. {fmt_gs(r['precio_gs'])}**")
                    ya_esta = any(
                        c["codigo"] == r["codigo"]
                        for c in st.session_state.comp_list
                    )
                    with rc4:
                        if st.button(
                            "✓" if ya_esta else "➕",
                            key=f"add_comp_{r['id']}",
                            disabled=ya_esta,
                            help="Ya agregado" if ya_esta else "Agregar como componente",
                        ):
                            st.session_state.comp_list.append({
                                "codigo":      r["codigo"],
                                "descripcion": r["descripcion"] or "",
                                "unidad":      r["unidad"] or "",
                                "clase":       r["class"],
                                "coef":        1.0,
                                "precio_gs":   float(r["precio_gs"] or 0),
                            })
                            st.rerun()

    # ---- Lista de componentes seleccionados ----
    if st.session_state.comp_list:
        st.markdown("**Componentes agregados:**")

        # DataFrame editable para los coeficientes
        df_comp = pd.DataFrame(st.session_state.comp_list)
        df_comp["total"] = df_comp["coef"] * df_comp["precio_gs"]

        df_show = df_comp[[
            "codigo", "clase", "descripcion", "unidad",
            "coef", "precio_gs", "total",
        ]].copy()

        edited = st.data_editor(
            df_show,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            column_config={
                "codigo":      st.column_config.TextColumn("Código", disabled=True, width=140),
                "clase":       st.column_config.TextColumn("Clase",  disabled=True, width=70),
                "descripcion": st.column_config.TextColumn("Descripción", disabled=True, width="large"),
                "unidad":      st.column_config.TextColumn("Unidad", disabled=True, width=60),
                "coef":        st.column_config.NumberColumn(
                    "Coeficiente",
                    min_value=0.0, step=0.01, format="%.4f",
                    help="Cantidad del componente por unidad de servicio",
                ),
                "precio_gs":   st.column_config.NumberColumn("Precio Gs.", disabled=True, format="%d"),
                "total":       st.column_config.NumberColumn("Subtotal Gs.", disabled=True, format="%d"),
            },
            key="comp_editor",
        )

        # Sincronizar coefs editados de vuelta a session_state
        for i, c in enumerate(st.session_state.comp_list):
            c["coef"] = float(edited.iloc[i]["coef"])

        # Botones para quitar componentes
        cols_rm = st.columns(min(len(st.session_state.comp_list), 6))
        for i, c in enumerate(st.session_state.comp_list):
            with cols_rm[i % len(cols_rm)]:
                if st.button(
                    f"🗑 {c['codigo']}",
                    key=f"rm_comp_{i}_{c['codigo']}",
                    use_container_width=True,
                    help="Quitar este componente",
                ):
                    st.session_state.comp_list.pop(i)
                    st.rerun()

        # Total del servicio
        total_serv = sum(
            c["coef"] * c["precio_gs"] for c in st.session_state.comp_list
        )
        st.metric(
            "Precio total del servicio (×1 unidad)",
            f"Gs. {fmt_gs(total_serv)}",
        )
    else:
        st.info("Buscá y agregá componentes para definir la composición del servicio.")

    st.divider()

    # ---- Crear servicio ----
    if st.button(
        "🏗️ Crear servicio",
        type="primary",
        key="btn_crear_serv",
        disabled=not st.session_state.comp_list,
    ):
        try:
            new_id = crear_servicio(
                codigo         = codigo_pred_s,
                clase          = clase_s,
                descripcion_es = desc_s,
                unidad         = unidad_s,
                componentes    = [
                    {"codigo": c["codigo"], "coef": c["coef"]}
                    for c in st.session_state.comp_list
                ],
                capitulo       = cap_s,
                subcapitulo    = subcap_s.strip() or None,
            )
            recalcular_precios_cascade(moneda="gs")
            st.success(
                f"✅ Servicio creado: **{codigo_pred_s}** (id={new_id}) con "
                f"{len(st.session_state.comp_list)} componente(s)."
            )
            st.balloons()
            # Limpiar
            st.session_state.comp_list = []
            for k in ["s_desc", "s_unidad", "s_subcap", "comp_busq"]:
                st.session_state.pop(k, None)
        except ValueError as e:
            st.error(f"❌ {e}")


# ===========================================================================
# TAB 3 — Listado, edición y borrado
# ===========================================================================

def _form_editar_hoja(item_id: int) -> None:
    """Renderiza el formulario inline de edición para una hoja custom."""
    full = get_detalle_partida(item_id)
    if not full:
        st.error("Ítem no encontrado.")
        return

    e1, e2 = st.columns(2)
    with e1:
        new_desc_es = st.text_area(
            "Descripción ES",
            value=full.get("descripcion_es") or "",
            key=f"e_desc_es_{item_id}",
            height=80,
        )
        new_desc_pt = st.text_area(
            "Descripción PT (opcional)",
            value=full.get("descripcion_pt") or "",
            key=f"e_desc_pt_{item_id}",
            height=60,
        )
        new_unidad = st.text_input(
            "Unidad",
            value=full.get("unidad") or "",
            key=f"e_unidad_{item_id}",
        )
    with e2:
        # Capítulo: dropdown con valor actual + opción libre
        caps_opts = ["(Sin capítulo)"] + get_capitulos_distintos() + ["+ Otro capítulo…"]
        cur_cap   = full.get("capitulo") or "(Sin capítulo)"
        cap_idx   = caps_opts.index(cur_cap) if cur_cap in caps_opts else 0
        sel_cap   = st.selectbox(
            "Capítulo", caps_opts, index=cap_idx,
            key=f"e_cap_sel_{item_id}",
        )
        if sel_cap == "+ Otro capítulo…":
            new_cap = st.text_input("Capítulo (libre)", key=f"e_cap_libre_{item_id}").strip() or None
        elif sel_cap == "(Sin capítulo)":
            new_cap = None
        else:
            new_cap = sel_cap

        new_subcap = st.text_input(
            "Subcapítulo",
            value=full.get("subcapitulo") or "",
            key=f"e_subcap_{item_id}",
        )
        ep1, ep2 = st.columns([2, 3])
        with ep1:
            new_precio = st.number_input(
                "Precio Gs.",
                min_value=0.0, step=500.0, format="%g",
                value=float(full.get("precio_gs") or 0),
                key=f"e_precio_{item_id}",
            )
        with ep2:
            new_fuente = st.text_input(
                "Fuente",
                value=full.get("precio_gs_fuente") or "",
                key=f"e_fuente_{item_id}",
            )

    bs, bc = st.columns([1, 1])
    if bs.button("💾 Guardar cambios", key=f"e_save_{item_id}", type="primary",
                 use_container_width=True):
        res = actualizar_item_hoja_custom(
            item_id,
            descripcion_es = new_desc_es,
            descripcion_pt = new_desc_pt,
            unidad         = new_unidad,
            capitulo       = new_cap if new_cap is not None else "",
            subcapitulo    = new_subcap,
            precio_gs      = new_precio if new_precio > 0 else None,
            fuente         = new_fuente,
        )
        if res["ok"]:
            st.toast(res["msg"], icon="✅")
            st.session_state.pop(f"editing_{item_id}", None)
            st.rerun()
        else:
            st.error(res["msg"])
    if bc.button("✕ Cancelar", key=f"e_cancel_{item_id}", use_container_width=True):
        st.session_state.pop(f"editing_{item_id}", None)
        st.rerun()


def _form_editar_servicio(item_id: int) -> None:
    """Renderiza el formulario inline de edición para un servicio custom."""
    full = get_detalle_partida(item_id)
    if not full:
        st.error("Servicio no encontrado.")
        return

    # ---- Metadata ----
    e1, e2 = st.columns(2)
    with e1:
        new_desc_es = st.text_area(
            "Descripción ES",
            value=full.get("descripcion_es") or "",
            key=f"se_desc_es_{item_id}",
            height=80,
        )
        new_desc_pt = st.text_area(
            "Descripción PT (opcional)",
            value=full.get("descripcion_pt") or "",
            key=f"se_desc_pt_{item_id}",
            height=60,
        )
    with e2:
        new_unidad = st.text_input(
            "Unidad",
            value=full.get("unidad") or "",
            key=f"se_unidad_{item_id}",
        )
        caps_opts = ["(Sin capítulo)"] + get_capitulos_distintos() + ["+ Otro capítulo…"]
        cur_cap   = full.get("capitulo") or "(Sin capítulo)"
        cap_idx   = caps_opts.index(cur_cap) if cur_cap in caps_opts else 0
        sel_cap   = st.selectbox(
            "Capítulo", caps_opts, index=cap_idx,
            key=f"se_cap_sel_{item_id}",
        )
        if sel_cap == "+ Otro capítulo…":
            new_cap = st.text_input("Capítulo (libre)", key=f"se_cap_libre_{item_id}").strip() or None
        elif sel_cap == "(Sin capítulo)":
            new_cap = None
        else:
            new_cap = sel_cap

        new_subcap = st.text_input(
            "Subcapítulo",
            value=full.get("subcapitulo") or "",
            key=f"se_subcap_{item_id}",
        )

    # ---- Composición editable ----
    st.markdown("##### Composición")
    edit_comp_key = f"edit_comp_list_{item_id}"

    # Cargar composición actual si todavía no está en session_state
    if edit_comp_key not in st.session_state:
        df_comp = get_componentes_servicio_custom(item_id)
        st.session_state[edit_comp_key] = [
            {
                "codigo":      r["codigo"],
                "descripcion": r["descripcion"] or "",
                "unidad":      r["unidad"] or "",
                "clase":       r["class"],
                "coef":        float(r["coef"]),
                "precio_gs":   float(r["precio_gs"] or 0),
            }
            for _, r in df_comp.iterrows()
        ]

    # Buscador para agregar componentes
    sb1, sb2 = st.columns([4, 1])
    with sb1:
        busq_e = st.text_input(
            "🔍 Buscar componente para agregar",
            key=f"se_busq_{item_id}",
            placeholder="Código o descripción (mín. 2 caracteres)",
        )
    with sb2:
        st.write("")
        st.write("")
        if st.button("🔄 Recargar", key=f"se_reload_{item_id}",
                     use_container_width=True,
                     help="Descartar cambios y recargar composición original"):
            st.session_state.pop(edit_comp_key, None)
            st.rerun()

    if busq_e and len(busq_e.strip()) >= 2:
        df_res = buscar_para_componente(busq_e.strip(), limit=15)
        if df_res.empty:
            st.info("Sin resultados.")
        else:
            with st.container(border=True):
                for _, r in df_res.iterrows():
                    if int(r["id"]) == item_id:
                        continue  # no auto-referencia
                    rc1, rc2, rc3, rc4 = st.columns([3, 4, 2, 1])
                    rc1.markdown(f"`{r['codigo']}` · _{r['class']}_")
                    rc2.caption((r["descripcion"] or "")[:80])
                    rc3.caption(f"Gs. {fmt_gs(r['precio_gs'])}")
                    ya_esta = any(
                        c["codigo"] == r["codigo"]
                        for c in st.session_state[edit_comp_key]
                    )
                    if rc4.button(
                        "✓" if ya_esta else "➕",
                        key=f"se_add_{item_id}_{r['id']}",
                        disabled=ya_esta,
                    ):
                        st.session_state[edit_comp_key].append({
                            "codigo":      r["codigo"],
                            "descripcion": r["descripcion"] or "",
                            "unidad":      r["unidad"] or "",
                            "clase":       r["class"],
                            "coef":        1.0,
                            "precio_gs":   float(r["precio_gs"] or 0),
                        })
                        st.rerun()

    # Editor de composición actual
    if st.session_state[edit_comp_key]:
        df_show = pd.DataFrame(st.session_state[edit_comp_key])
        df_show["total"] = df_show["coef"] * df_show["precio_gs"]
        df_disp = df_show[["codigo", "clase", "descripcion", "unidad",
                            "coef", "precio_gs", "total"]].copy()

        edited = st.data_editor(
            df_disp,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            column_config={
                "codigo":      st.column_config.TextColumn("Código", disabled=True, width=140),
                "clase":       st.column_config.TextColumn("Clase",  disabled=True, width=70),
                "descripcion": st.column_config.TextColumn("Descripción", disabled=True, width="large"),
                "unidad":      st.column_config.TextColumn("Unidad", disabled=True, width=60),
                "coef":        st.column_config.NumberColumn(
                    "Coeficiente",
                    min_value=0.0, step=0.01, format="%.4f",
                ),
                "precio_gs":   st.column_config.NumberColumn("Precio Gs.", disabled=True, format="%d"),
                "total":       st.column_config.NumberColumn("Subtotal Gs.", disabled=True, format="%d"),
            },
            key=f"se_comp_editor_{item_id}",
        )

        # Sincronizar coefs editados
        for i, c in enumerate(st.session_state[edit_comp_key]):
            c["coef"] = float(edited.iloc[i]["coef"])

        # Botones para quitar componentes
        n_comp = len(st.session_state[edit_comp_key])
        cols_rm = st.columns(min(n_comp, 6))
        for i, c in enumerate(st.session_state[edit_comp_key]):
            with cols_rm[i % len(cols_rm)]:
                if st.button(
                    f"🗑 {c['codigo']}",
                    key=f"se_rm_{item_id}_{i}",
                    use_container_width=True,
                ):
                    st.session_state[edit_comp_key].pop(i)
                    st.rerun()

        total_serv = sum(c["coef"] * c["precio_gs"] for c in st.session_state[edit_comp_key])
        st.metric("Precio total estimado", f"Gs. {fmt_gs(total_serv)}")
    else:
        st.warning("⚠️ El servicio quedaría sin componentes. Agregá al menos uno antes de guardar.")

    # ---- Botones guardar / cancelar ----
    bs, bc = st.columns([1, 1])
    if bs.button(
        "💾 Guardar cambios",
        key=f"se_save_{item_id}",
        type="primary",
        use_container_width=True,
        disabled=not st.session_state[edit_comp_key],
    ):
        res = actualizar_servicio_custom(
            item_id,
            descripcion_es = new_desc_es,
            descripcion_pt = new_desc_pt,
            unidad         = new_unidad,
            capitulo       = new_cap if new_cap is not None else "",
            subcapitulo    = new_subcap,
            componentes    = [
                {"codigo": c["codigo"], "coef": c["coef"]}
                for c in st.session_state[edit_comp_key]
            ],
        )
        if res["ok"]:
            st.toast(res["msg"], icon="✅")
            st.session_state.pop(f"editing_{item_id}",  None)
            st.session_state.pop(edit_comp_key,         None)
            st.rerun()
        else:
            st.error(res["msg"])
    if bc.button("✕ Cancelar", key=f"se_cancel_{item_id}", use_container_width=True):
        st.session_state.pop(f"editing_{item_id}", None)
        st.session_state.pop(edit_comp_key,        None)
        st.rerun()


with tab_lista:
    st.subheader("Mis ítems personalizados")

    df_custom = listar_items_custom()

    if df_custom.empty:
        st.info(
            "Todavía no creaste ningún ítem propio. "
            "Empezá en alguna de las pestañas anteriores."
        )
    else:
        st.caption(
            f"{len(df_custom)} ítem(s) personalizado(s). "
            f"Click en un ítem para expandir y editarlo."
        )

        fc1, fc2 = st.columns([2, 4])
        with fc1:
            tipos_disp = ["(Todos)"] + sorted(df_custom["class"].dropna().unique().tolist())
            tipo_filt  = st.selectbox("Tipo", tipos_disp, key="cust_filt_tipo")
        with fc2:
            busq_l = st.text_input(
                "🔍 Buscar",
                key="cust_filt_busq",
                placeholder="Por código o descripción",
            )

        df_view = df_custom.copy()
        if tipo_filt != "(Todos)":
            df_view = df_view[df_view["class"] == tipo_filt]
        if busq_l:
            q = busq_l.lower()
            df_view = df_view[
                df_view["codigo"].str.lower().str.contains(q, na=False) |
                df_view["descripcion_es"].str.lower().str.contains(q, na=False).fillna(False)
            ]

        if df_view.empty:
            st.info("Sin resultados con esos filtros.")
        else:
            for _, item in df_view.iterrows():
                item_id = int(item["id"])
                desc    = item["descripcion_es"] or item["descripcion_pt"] or "(sin descripción)"
                clase   = item["class"]
                icon    = "🔧" if (clase or "").startswith("SER.") else "📦"
                editing = st.session_state.get(f"editing_{item_id}", False)
                confirm = st.session_state.get(f"confirm_del_{item_id}", False)

                with st.expander(
                    f"{icon} **{item['codigo']}** · {clase} · {desc[:60]} "
                    f"— Gs. {fmt_gs(item['precio_gs'])}",
                    expanded=editing,
                ):
                    if editing:
                        # ---- Modo edición ----
                        if (clase or "").startswith("SER."):
                            _form_editar_servicio(item_id)
                        else:
                            _form_editar_hoja(item_id)
                    elif confirm:
                        # ---- Confirmación de borrado ----
                        st.warning(f"¿Confirmar eliminación de **{item['codigo']}**?")
                        cc1, cc2 = st.columns([1, 1])
                        if cc1.button("⚠️ Sí, eliminar", key=f"confirm_btn_{item_id}",
                                      type="primary", use_container_width=True):
                            res = eliminar_item_custom(item_id)
                            if res["ok"]:
                                st.toast(res["msg"], icon="🗑️")
                                st.session_state.pop(f"confirm_del_{item_id}", None)
                                st.rerun()
                            else:
                                st.error(res["msg"])
                                st.session_state.pop(f"confirm_del_{item_id}", None)
                        if cc2.button("✕ Cancelar", key=f"cancel_btn_{item_id}",
                                      use_container_width=True):
                            st.session_state.pop(f"confirm_del_{item_id}", None)
                            st.rerun()
                    else:
                        # ---- Vista resumen + acciones ----
                        di1, di2 = st.columns([4, 1])
                        with di1:
                            st.markdown(f"**Descripción:** {desc}")
                            st.caption(
                                f"Unidad: **{item['unidad'] or '—'}** · "
                                f"Capítulo: {item['capitulo'] or '—'} · "
                                f"Subcap.: {item['subcapitulo'] or '—'}"
                            )
                        with di2:
                            if st.button("✏️ Editar", key=f"edit_btn_{item_id}",
                                         use_container_width=True, type="primary"):
                                st.session_state[f"editing_{item_id}"] = True
                                st.rerun()
                            if st.button("🗑️ Eliminar", key=f"del_btn_{item_id}",
                                         use_container_width=True):
                                st.session_state[f"confirm_del_{item_id}"] = True
                                st.rerun()
