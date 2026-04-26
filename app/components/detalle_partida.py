"""detalle_partida.py — Panel de detalle de una partida TCPO."""
import pandas as pd
import streamlit as st

from app.utils.formatters import (
    clase_label, fmt_brl, fmt_coef, fmt_gs, relevancia_badge, relevancia_color,
)
from app.utils.queries import (
    agregar_favorito, esta_en_favoritos, get_detalle_partida,
    get_insumos_de_partida, get_nota_partida, guardar_nota_partida,
    get_proyectos, actualizar_precio_insumo_gs, recalcular_precios_cascade,
    get_glosario, actualizar_descripcion_es, toggle_revision,
)


def panel_detalle(tcpo_item_id: int, proyecto_id: int | None = None) -> None:
    """Renderiza el panel de detalle para un tcpo_item_id dado."""
    item = get_detalle_partida(tcpo_item_id)
    if not item:
        st.info("Seleccioná una partida para ver el detalle.")
        return

    rel        = item.get("relevancia_py") or "sin_clasificar"
    color      = relevancia_color(rel)
    clase      = item.get("class") or ""
    en_rev     = bool(item.get("en_revision"))

    # --- encabezado con botón de revisión ---
    rev_badge = " &nbsp;🔬 <b style='color:#f0a500'>En revisión</b>" if en_rev else ""
    h1, h2 = st.columns([5, 1])
    with h1:
        st.markdown(
            f"<div style='border-left:4px solid {color}; padding:6px 10px; "
            f"background:rgba(0,0,0,0.04); border-radius:4px; margin-bottom:8px'>"
            f"<b>{item.get('codigo','')}</b> &nbsp;·&nbsp; "
            f"<span style='color:{color}'>{relevancia_badge(rel)}</span> &nbsp;·&nbsp; "
            f"{clase_label(clase)}{rev_badge}"
            f"</div>",
            unsafe_allow_html=True,
        )
    with h2:
        rev_btn_label = "✅ OK" if en_rev else "🔬"
        rev_btn_help  = "Quitar de revisión" if en_rev else "Marcar para revisar traducción"
        if st.button(rev_btn_label, key=f"rev_{tcpo_item_id}", help=rev_btn_help,
                     type="secondary", use_container_width=True):
            toggle_revision(tcpo_item_id)
            st.rerun()

    # --- descripción ES editable ---
    desc_es = item.get("descripcion_es") or ""
    edit_key = f"edit_desc_{tcpo_item_id}"

    if st.session_state.get(edit_key):
        nueva_desc = st.text_area(
            "Descripción ES",
            value=desc_es,
            height=80,
            key=f"ta_desc_{tcpo_item_id}",
            label_visibility="collapsed",
        )
        c1, c2 = st.columns([1, 1])
        if c1.button("💾 Guardar", key=f"save_desc_{tcpo_item_id}", type="primary"):
            actualizar_descripcion_es(tcpo_item_id, nueva_desc)
            st.session_state.pop(edit_key, None)
            st.toast("Descripción actualizada", icon="✅")
            st.rerun()
        if c2.button("✕ Cancelar", key=f"cancel_desc_{tcpo_item_id}"):
            st.session_state.pop(edit_key, None)
            st.rerun()
    else:
        dc1, dc2 = st.columns([5, 1])
        with dc1:
            if desc_es:
                st.markdown(f"**{desc_es}**")
            else:
                st.caption("*(sin traducción)*")
        with dc2:
            if st.button("✏️", key=f"btn_edit_desc_{tcpo_item_id}", help="Editar descripción"):
                st.session_state[edit_key] = True
                st.rerun()

    just = item.get("relevancia_justificacion") or ""
    if just:
        st.caption(f"_{just}_")

    desc_pt = item.get("descripcion_pt") or ""
    if desc_pt:
        with st.expander("Descripción PT original"):
            st.text(desc_pt)

    # --- Sugerencias de glosario ---
    if desc_pt:
        df_glos = get_glosario()
        desc_pt_lower = desc_pt.lower()
        matches = df_glos[df_glos["termino_pt"].str.lower().apply(lambda t: t in desc_pt_lower)]
        if not matches.empty:
            with st.expander(f"📖 Glosario ({len(matches)} término{'s' if len(matches) > 1 else ''} encontrado{'s' if len(matches) > 1 else ''})"):
                for _, g in matches.iterrows():
                    cat = f" _{g['categoria']}_ " if g.get("categoria") else ""
                    st.markdown(f"**{g['termino_pt']}**{cat}→ {g['termino_es']}")

    st.divider()

    # --- datos técnicos: priorizar GS sobre BRL ---
    precio_gs    = item.get("precio_gs")
    total_gs     = item.get("precio_total_gs")
    precio_brl   = item.get("precio_brl")

    c1, c2 = st.columns(2)
    with c1:
        st.metric("Unidad", item.get("unidad") or "—")
        if clase and clase.startswith("SER."):
            st.metric("Coeficiente", fmt_coef(item.get("coef")))
    with c2:
        if precio_gs:
            st.metric("Precio ref. Gs.", fmt_gs(precio_gs))
            st.metric("Total Gs.",       fmt_gs(total_gs))
        else:
            st.metric("Precio ref. BRL", fmt_brl(precio_brl))
            st.metric("Total BRL",       fmt_brl(item.get("precio_total_brl")))

    # Editor de precio para insumos primarios (no servicios)
    if not (clase and clase.startswith("SER.")):
        with st.expander("✏️ Editar precio Gs."):
            fuente_actual = item.get("precio_gs_fuente") or ""
            nuevo_precio = st.number_input(
                "Precio Gs.",
                value=float(precio_gs or 0),
                min_value=0.0,
                step=500.0,
                format="%g",
                key=f"precio_input_{tcpo_item_id}",
            )
            nueva_fuente = st.text_input(
                "Fuente",
                value=fuente_actual,
                placeholder="ej: Mandu'a mar-2026, Cotización, MOPC…",
                key=f"fuente_input_{tcpo_item_id}",
            )
            if st.button("💾 Guardar precio", key=f"save_precio_{tcpo_item_id}",
                         type="primary", use_container_width=True):
                actualizar_precio_insumo_gs(
                    item["codigo"], nuevo_precio, nueva_fuente
                )
                r = recalcular_precios_cascade(moneda="gs")
                st.toast(
                    f"✅ Precio guardado · {r['servicios_p2']:,} servicios recalculados",
                    icon="✅",
                )
                st.rerun()

    # --- capítulo / subcapítulo ---
    cap    = item.get("capitulo") or ""
    subcap = item.get("subcapitulo") or ""
    if cap:
        st.caption(f"📁 {cap}")
    if subcap:
        st.caption(f"   └ {subcap}")

    # --- desglose de insumos con editor de precios ---
    if clase and clase.startswith("SER."):
        df_ins = get_insumos_de_partida(tcpo_item_id)
        if not df_ins.empty:
            with st.expander(f"Desglose de insumos ({len(df_ins)} items)"):

                mask_ser = df_ins["class"].str.startswith("SER.", na=False)
                df_pri   = df_ins[~mask_ser].reset_index(drop=True)
                df_subs  = df_ins[mask_ser].reset_index(drop=True)

                # --- Insumos primarios (MAT., M.O., etc.) — editables ---
                if not df_pri.empty:
                    st.caption("📦 Insumos primarios")
                    df_show = pd.DataFrame({
                        "Clase":       df_pri["class"],
                        "Código":      df_pri["codigo"],
                        "Descripción": df_pri["descripcion_es"].fillna(df_pri["descripcion_pt"]),
                        "Unidad":      df_pri["unidad"],
                        "Coef.":       df_pri["coef"].round(4),
                        "Precio Gs.":  df_pri["precio_gs"],
                        "Fuente":      df_pri["precio_gs_fuente"],
                        "Total Gs.":   df_pri["precio_total_gs"],
                        "Ref. BRL":    df_pri["precio_brl"],
                    })

                    edited = st.data_editor(
                        df_show,
                        use_container_width=True,
                        hide_index=True,
                        num_rows="fixed",
                        column_config={
                            "Clase":       st.column_config.TextColumn(width=70,  disabled=True),
                            "Código":      st.column_config.TextColumn(width=150, disabled=True),
                            "Descripción": st.column_config.TextColumn(width="large", disabled=True),
                            "Unidad":      st.column_config.TextColumn(width=55,  disabled=True),
                            "Coef.":       st.column_config.NumberColumn(width=65, disabled=True, format="%.4f"),
                            "Precio Gs.":  st.column_config.NumberColumn(
                                width=110, min_value=0, step=500, format="%d",
                                help="✏️ Precio unitario en Guaraníes",
                            ),
                            "Fuente":      st.column_config.TextColumn(
                                width=130,
                                help="✏️ Origen del precio (ej: Mandu'a mar-2026, Cotización, MOPC)",
                            ),
                            "Total Gs.":   st.column_config.NumberColumn(width=110, disabled=True, format="%d"),
                            "Ref. BRL":    st.column_config.NumberColumn(width=85,  disabled=True, format="%.4f"),
                        },
                        key=f"desglose_editor_{tcpo_item_id}",
                    )

                    if st.button("💾 Guardar precios Gs.", key=f"guardar_gs_{tcpo_item_id}",
                                 type="primary", use_container_width=True):
                        orig_gs     = df_show["Precio Gs."].fillna(0)
                        edited_gs   = edited["Precio Gs."].fillna(0)
                        orig_fuente = df_show["Fuente"].fillna("")
                        edit_fuente = edited["Fuente"].fillna("")

                        changed = edited[
                            (edited_gs.round(0) != orig_gs.round(0)) |
                            (edit_fuente != orig_fuente)
                        ]

                        if changed.empty:
                            st.toast("Sin cambios")
                        else:
                            for _, row in changed.iterrows():
                                actualizar_precio_insumo_gs(
                                    row["Código"],
                                    float(row["Precio Gs."] or 0),
                                    str(row["Fuente"] or ""),
                                )
                            r = recalcular_precios_cascade(moneda="gs")
                            st.toast(
                                f"✅ {len(changed)} precio(s) guardado(s) · "
                                f"{r['servicios_p2']:,} servicios recalculados",
                                icon="✅",
                            )
                            st.rerun()

                # --- Sub-servicios SER.* — expandibles con editor propio ---
                if not df_subs.empty:
                    st.caption("🔧 Sub-servicios")
                    for si, (_, sub) in enumerate(df_subs.iterrows()):
                        desc      = (sub.get("descripcion_es") or sub.get("descripcion_pt") or "")[:60]
                        coef      = sub.get("coef", 1.0)
                        total_gs  = sub.get("precio_total_gs")
                        precio_gs = sub.get("precio_gs")

                        if precio_gs:
                            precio_str = f"Gs. {fmt_gs(precio_gs)} · total {fmt_gs(total_gs)}"
                        elif sub.get("precio_brl"):
                            precio_str = f"ref. {fmt_brl(sub['precio_brl'])} BRL"
                        else:
                            precio_str = "sin precio"

                        label  = f"🔧 {sub['codigo']} — {desc} (×{coef:.4f} · {precio_str})"
                        sub_id = sub["id"]

                        # Componentes del sub-servicio: recursivo
                        # (maneja tanto TCPO original como custom via item_composicion)
                        df_sub_c = get_insumos_de_partida(sub_id)

                        with st.expander(label):
                            if df_sub_c.empty:
                                st.info("Sin composición disponible.")
                            else:
                                ekey = f"sub_editor_{tcpo_item_id}_{si}"
                                df_sc = pd.DataFrame({
                                    "Clase":       df_sub_c["class"],
                                    "Código":      df_sub_c["codigo"],
                                    "Descripción": df_sub_c["descripcion_es"].fillna(df_sub_c["descripcion_pt"]),
                                    "Unidad":      df_sub_c["unidad"],
                                    "Coef.":       df_sub_c["coef"].round(4),
                                    "Precio Gs.":  df_sub_c["precio_gs"],
                                    "Fuente":      df_sub_c["precio_gs_fuente"],
                                    "Total Gs.":   df_sub_c["precio_total_gs"],
                                    "Ref. BRL":    df_sub_c["precio_brl"],
                                })
                                edited_sc = st.data_editor(
                                    df_sc,
                                    use_container_width=True,
                                    hide_index=True,
                                    num_rows="fixed",
                                    column_config={
                                        "Clase":       st.column_config.TextColumn(width=70,  disabled=True),
                                        "Código":      st.column_config.TextColumn(width=150, disabled=True),
                                        "Descripción": st.column_config.TextColumn(width="large", disabled=True),
                                        "Unidad":      st.column_config.TextColumn(width=55,  disabled=True),
                                        "Coef.":       st.column_config.NumberColumn(width=65, disabled=True, format="%.4f"),
                                        "Precio Gs.":  st.column_config.NumberColumn(width=110, min_value=0, step=500, format="%d"),
                                        "Fuente":      st.column_config.TextColumn(width=130),
                                        "Total Gs.":   st.column_config.NumberColumn(width=110, disabled=True, format="%d"),
                                        "Ref. BRL":    st.column_config.NumberColumn(width=85,  disabled=True, format="%.4f"),
                                    },
                                    key=ekey,
                                )
                                if st.button("💾 Guardar", key=f"save_{ekey}", type="primary"):
                                    orig_gs  = df_sc["Precio Gs."].fillna(0)
                                    edit_gs  = edited_sc["Precio Gs."].fillna(0)
                                    orig_f   = df_sc["Fuente"].fillna("")
                                    edit_f   = edited_sc["Fuente"].fillna("")
                                    changed  = edited_sc[
                                        (edit_gs.round(0) != orig_gs.round(0)) | (edit_f != orig_f)
                                    ]
                                    if changed.empty:
                                        st.toast("Sin cambios")
                                    else:
                                        for _, row in changed.iterrows():
                                            actualizar_precio_insumo_gs(
                                                row["Código"],
                                                float(row["Precio Gs."] or 0),
                                                str(row["Fuente"] or ""),
                                            )
                                        r = recalcular_precios_cascade(moneda="gs")
                                        st.toast(
                                            f"✅ {len(changed)} precio(s) guardado(s) · "
                                            f"{r['servicios_p2']:,} servicios recalculados",
                                            icon="✅",
                                        )
                                        st.rerun()

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
        proy_opts   = {row["nombre"]: row["id"] for _, row in df_proyectos.iterrows()}
        default_idx = 0
        if proyecto_id:
            ids = list(proy_opts.values())
            if proyecto_id in ids:
                default_idx = ids.index(proyecto_id)

        sel_nombre  = st.selectbox(
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
