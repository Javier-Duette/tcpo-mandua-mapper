"""4_configuracion.py — Traducción adicional, glosario y estado del sistema."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import subprocess
import streamlit as st
import pandas as pd

from app.utils.queries import (
    get_cobertura_por_capitulo, get_glosario, upsert_glosario_termino, eliminar_glosario_termino,
    get_mandua_precios, actualizar_precio_mandua,
    get_insumos_primarios_unicos, actualizar_precio_insumo_gs, recalcular_precios_cascade,
)
from app.utils.formatters import fmt_pct

st.set_page_config(page_title="Configuración — TCPO PY", layout="wide",
                   page_icon="⚙️", initial_sidebar_state="collapsed")

st.title("⚙️ Configuración")

tab_trad, tab_tcpo_precios, tab_precios, tab_glos, tab_about = st.tabs(
    ["🌐 Traducir capítulos", "🔧 Precios TCPO", "💰 Precios Mandu'a", "📖 Glosario", "ℹ️ Acerca de"]
)

# ============================================================
# TAB 1 — Traducir capítulos adicionales
# ============================================================
with tab_trad:
    st.subheader("Traducir capítulos adicionales")
    st.caption("Seleccioná capítulos con traducción pendiente y lanzá el proceso A2.")

    df_cob = get_cobertura_por_capitulo()
    df_cob["pct_trad"] = (
        df_cob["traducidos"] / df_cob["total"].replace(0, 1) * 100
    ).round(0).astype(int)
    df_cob["pendientes"] = df_cob["total"] - df_cob["traducidos"]

    # Mostrar tabla de cobertura
    st.dataframe(
        df_cob[["capitulo", "total", "traducidos", "pendientes", "pct_trad"]].rename(columns={
            "capitulo":   "Capítulo",
            "total":      "Total",
            "traducidos": "Traducidos",
            "pendientes": "Pendientes",
            "pct_trad":   "% Trad.",
        }),
        use_container_width=True,
        hide_index=True,
        column_config={
            "% Trad.": st.column_config.ProgressColumn("% Trad.", min_value=0, max_value=100),
        },
    )

    st.divider()

    # Selector de capítulos a traducir
    caps_con_pendientes = df_cob[df_cob["pendientes"] > 0]["capitulo"].tolist()
    if not caps_con_pendientes:
        st.success("✅ Todos los capítulos están completamente traducidos.")
    else:
        sel_caps = st.multiselect(
            "Capítulos a traducir",
            options=caps_con_pendientes,
            key="conf_caps_sel",
            format_func=lambda c: f"{c} ({int(df_cob[df_cob['capitulo']==c]['pendientes'].values[0]):,} pendientes)",
        )

        if sel_caps:
            n_pendientes = int(df_cob[df_cob["capitulo"].isin(sel_caps)]["pendientes"].sum())
            est_usd      = n_pendientes * 0.0033 / 100
            est_min      = round(n_pendientes / 40 * 0.6)

            st.info(
                f"**{n_pendientes:,}** ítems únicos pendientes · "
                f"Costo estimado: **USD {est_usd:.3f}** · "
                f"Tiempo estimado: ~{est_min} min"
            )

            if st.button("🚀 Lanzar traducción", type="primary", key="btn_lanzar_trad"):
                caps_codigos = [c[:2].strip() for c in sel_caps]
                cmd = [
                    sys.executable,
                    str(ROOT / "scripts" / "A2_traducir_y_clasificar.py"),
                    "--capitulos", *caps_codigos,
                ]
                st.info(f"Ejecutando: `{' '.join(cmd)}`")
                with st.spinner("Procesando… (puede tomar varios minutos)"):
                    try:
                        result = subprocess.run(
                            cmd, capture_output=True, text=True, timeout=7200,
                            input="y\n",
                        )
                        if result.returncode == 0:
                            st.success("✅ Traducción completada.")
                            st.code(result.stdout[-3000:], language=None)
                        else:
                            st.error("❌ Error durante la traducción.")
                            st.code(result.stderr[-2000:], language=None)
                    except subprocess.TimeoutExpired:
                        st.error("Tiempo de espera agotado (2 h). "
                                 "Ejecutá el script desde la terminal directamente.")

# ============================================================
# TAB 2 — Precios TCPO (insumos primarios + cascade)
# ============================================================
with tab_tcpo_precios:
    st.subheader("Precios de insumos TCPO en Guaraníes")
    st.caption(
        "Ingresá el precio en **Gs.** para cada insumo primario (M.O., MAT., EQ.). "
        "Al guardar se recalculan automáticamente los totales de todos los servicios que lo usan. "
        "El precio BRL original queda como referencia."
    )

    clase_sel = st.radio(
        "Clase",
        options=["M.O.", "MAT.", "EQ.AQ.", "SER.MO", "EQ.LOC"],
        horizontal=True,
        key="tcpo_clase_sel",
    )

    busq_tcpo = st.text_input(
        "Filtrar",
        placeholder="ej: pedreiro, bloco, cimento…",
        key="tcpo_busq",
    )

    df_ins = get_insumos_primarios_unicos()
    df_ins = df_ins[df_ins["Clase"] == clase_sel]
    if busq_tcpo:
        df_ins = df_ins[
            df_ins["Descripcion"].str.contains(busq_tcpo, case=False, na=False) |
            df_ins["Codigo"].str.contains(busq_tcpo, case=False, na=False)
        ]

    st.caption(f"{len(df_ins):,} insumos · la columna **Precio BRL** es editable")

    edited_tcpo = st.data_editor(
        df_ins.reset_index(drop=True),
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config={
            "Codigo":      st.column_config.TextColumn("Código",       disabled=True, width="small"),
            "Clase":       st.column_config.TextColumn("Clase",        disabled=True, width=60),
            "Descripcion": st.column_config.TextColumn("Descripción",  disabled=True, width="large"),
            "Unidad":      st.column_config.TextColumn("Unidad",       disabled=True, width=60),
            "Precio_BRL":  st.column_config.NumberColumn(
                "Ref. BRL", disabled=True, format="%.4f", width="small",
                help="Precio de referencia original en Reales brasileños (solo lectura)",
            ),
            "Precio_GS":   st.column_config.NumberColumn(
                "Precio Gs.", min_value=0, step=500, format="%d", width="medium",
                help="Precio en Guaraníes para Paraguay — editá este campo",
            ),
            "Fuente":      st.column_config.TextColumn(
                "Fuente", width="medium",
                help="Origen del precio (ej: Mandu'a mar-2026, Cotización, MOPC)",
            ),
            "Usos": st.column_config.NumberColumn(
                "Usos", disabled=True, width=55,
                help="Cantidad de servicios que usan este insumo",
            ),
        },
        key=f"editor_tcpo_{clase_sel}",
    )

    col_s, col_warn = st.columns([2, 5])
    with col_s:
        guardar = st.button("💾 Guardar y recalcular", type="primary", key="btn_guardar_tcpo")
    with col_warn:
        st.caption("⚠️ Recalcula **precio_total_gs** de todos los servicios en cascada.")

    if guardar:
        df_orig = get_insumos_primarios_unicos()
        df_orig = df_orig[df_orig["Clase"] == clase_sel]
        if busq_tcpo:
            df_orig = df_orig[
                df_orig["Descripcion"].str.contains(busq_tcpo, case=False, na=False) |
                df_orig["Codigo"].str.contains(busq_tcpo, case=False, na=False)
            ]
        df_orig = df_orig.reset_index(drop=True)

        orig_gs     = df_orig["Precio_GS"].fillna(0)
        edit_gs     = edited_tcpo["Precio_GS"].fillna(0)
        orig_fuente = df_orig["Fuente"].fillna("")
        edit_fuente = edited_tcpo["Fuente"].fillna("")
        changed_mask = (edit_gs.round(0) != orig_gs.round(0)) | (edit_fuente != orig_fuente)
        df_changed   = edited_tcpo[changed_mask]

        if df_changed.empty:
            st.info("No hay cambios para guardar.")
        else:
            with st.spinner(f"Guardando {len(df_changed)} precio(s) y recalculando cascade…"):
                for _, row in df_changed.iterrows():
                    actualizar_precio_insumo_gs(
                        row["Codigo"],
                        float(row["Precio_GS"] or 0),
                        str(row["Fuente"] or ""),
                    )
                resultado = recalcular_precios_cascade(moneda="gs")
            st.success(
                f"✅ {len(df_changed)} insumo(s) actualizados en Gs. "
                f"Cascade: {resultado['insumos']:,} totales · "
                f"{resultado['servicios_p2']:,} servicios recalculados."
            )
            st.rerun()


# ============================================================
# TAB 3 — Precios Mandu'a
# ============================================================
with tab_precios:
    st.subheader("Actualizar precios Mandu'a")
    st.caption("Editá el precio unitario (Gs.) directamente en la tabla. "
               "Los cambios se guardan al hacer clic en **Guardar cambios**.")

    tipo_sel = st.radio(
        "Tabla",
        options=["materiales", "mano_obra"],
        format_func=lambda t: "🧱 Materiales" if t == "materiales" else "👷 Mano de obra",
        horizontal=True,
        key="conf_mandua_tipo",
    )

    # Búsqueda rápida dentro de la tabla
    busq_precio = st.text_input(
        "Filtrar por descripción o sección",
        placeholder="ej: cemento, arena, oficial…",
        key="conf_mandua_busq",
    )

    df_m = get_mandua_precios(tipo_sel)
    if busq_precio:
        mask = (
            df_m["descripcion"].str.contains(busq_precio, case=False, na=False) |
            df_m["seccion"].str.contains(busq_precio, case=False, na=False)
        )
        df_m = df_m[mask]

    st.caption(f"{len(df_m):,} ítems")

    edited = st.data_editor(
        df_m,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config={
            "id":          st.column_config.NumberColumn("ID",        disabled=True, width="small"),
            "seccion":     st.column_config.TextColumn("Sección",     disabled=True, width="medium"),
            "descripcion": st.column_config.TextColumn("Descripción", disabled=True, width="large"),
            "unidad":      st.column_config.TextColumn("Unidad",      disabled=True, width="small"),
            "precio_gs":   st.column_config.NumberColumn(
                "Precio Gs.", min_value=0, step=100, format="%d",
                width="medium",
            ),
        },
        key=f"editor_mandua_{tipo_sel}",
    )

    col_save, col_info = st.columns([2, 5])
    with col_save:
        if st.button("💾 Guardar cambios", type="primary", key="btn_guardar_mandua"):
            # Detectar filas modificadas comparando con original
            df_orig = get_mandua_precios(tipo_sel)
            if busq_precio:
                mask2 = (
                    df_orig["descripcion"].str.contains(busq_precio, case=False, na=False) |
                    df_orig["seccion"].str.contains(busq_precio, case=False, na=False)
                )
                df_orig = df_orig[mask2]

            changed = edited[edited["precio_gs"] != df_orig["precio_gs"].values[:len(edited)]]
            if changed.empty:
                st.info("No hay cambios para guardar.")
            else:
                for _, row in changed.iterrows():
                    actualizar_precio_mandua(tipo_sel, int(row["id"]), float(row["precio_gs"]))
                st.success(f"✅ {len(changed)} precio{'s' if len(changed) > 1 else ''} actualizado{'s' if len(changed) > 1 else ''}.")
                st.rerun()

    with col_info:
        st.caption("Solo la columna **Precio Gs.** es editable. "
                   "Las demás columnas son de referencia.")


# ============================================================
# TAB 3 — Glosario
# ============================================================
with tab_glos:
    st.subheader("Glosario PT → ES Paraguay")

    df_glos = get_glosario()

    # --- Filtros ---
    fc1, fc2 = st.columns([3, 2])
    with fc1:
        busq_glos = st.text_input("🔍 Buscar término", placeholder="PT o ES…", key="glos_busq")
    with fc2:
        cats_disponibles = ["Todas"] + sorted(df_glos["categoria"].dropna().unique().tolist())
        cat_filtro = st.selectbox("Categoría", cats_disponibles, key="glos_cat_filtro")

    df_view = df_glos.copy()
    if busq_glos:
        q = busq_glos.lower()
        df_view = df_view[
            df_view["termino_pt"].str.lower().str.contains(q, na=False) |
            df_view["termino_es"].str.lower().str.contains(q, na=False)
        ]
    if cat_filtro != "Todas":
        df_view = df_view[df_view["categoria"] == cat_filtro]

    st.caption(f"{len(df_view)} de {len(df_glos)} términos · columnas **Término ES**, **Categoría** y **Notas** son editables")

    # --- Tabla editable ---
    disp_glos = df_view[["termino_pt", "termino_es", "categoria", "notas", "usos"]].copy()
    st.data_editor(
        disp_glos,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config={
            "termino_pt":  st.column_config.TextColumn("Término PT",  disabled=True, width="medium"),
            "termino_es":  st.column_config.TextColumn("Término ES",  width="medium"),
            "categoria":   st.column_config.TextColumn("Categoría",   width="small"),
            "notas":       st.column_config.TextColumn("Notas",       width="medium"),
            "usos":        st.column_config.NumberColumn("Usos",      disabled=True, width=60,
                                                          help="Cantidad de ítems TCPO que contienen este término"),
        },
        key="editor_glosario",
    )

    # --- Acciones ---
    btn_save, _, btn_del_area = st.columns([2, 1, 4])

    with btn_save:
        if st.button("💾 Guardar cambios", type="primary", key="btn_glos_save"):
            edited_df = st.session_state.get("editor_glosario", {}).get("edited_rows", {})
            if not edited_df:
                st.toast("Sin cambios")
            else:
                for idx, cambios in edited_df.items():
                    row = disp_glos.iloc[idx]
                    upsert_glosario_termino(
                        row["termino_pt"],
                        cambios.get("termino_es", row["termino_es"]),
                        cambios.get("categoria",  row["categoria"] or ""),
                        cambios.get("notas",      row["notas"] or ""),
                    )
                st.toast(f"✅ {len(edited_df)} término(s) actualizado(s)", icon="✅")
                st.rerun()

    with btn_del_area:
        if not disp_glos.empty:
            cd1, cd2 = st.columns([3, 1])
            pt_a_eliminar = cd1.selectbox(
                "Eliminar término",
                options=disp_glos["termino_pt"].tolist(),
                label_visibility="collapsed",
                key="glos_del_sel",
            )
            if cd2.button("🗑", key="btn_glos_del", help="Eliminar término seleccionado"):
                eliminar_glosario_termino(pt_a_eliminar)
                st.toast(f"Término «{pt_a_eliminar}» eliminado", icon="🗑️")
                st.rerun()

    # --- Agregar nuevo término ---
    st.divider()
    with st.expander("➕ Agregar nuevo término"):
        with st.form("form_glosario"):
            c1, c2 = st.columns(2)
            pt_new      = c1.text_input("Término PT",          key="glos_pt_new")
            es_new      = c2.text_input("Término ES",          key="glos_es_new")
            cat_new     = st.text_input("Categoría (opcional)", key="glos_cat_new")
            notas_new   = st.text_input("Notas (opcional)",    key="glos_notas_new")
            if st.form_submit_button("Guardar"):
                if pt_new.strip() and es_new.strip():
                    upsert_glosario_termino(pt_new.strip(), es_new.strip(), cat_new.strip(), notas_new.strip())
                    st.toast("Término guardado", icon="✅")
                    st.rerun()
                else:
                    st.error("PT y ES son obligatorios.")

# ============================================================
# TAB 3 — Acerca de
# ============================================================
with tab_about:
    st.subheader("Estado del sistema")

    from app.utils.queries import get_conn, DB_PATH
    conn = get_conn()

    stats_rows = conn.execute("""
        SELECT 'tcpo_items' AS tbl, COUNT(*) AS n FROM tcpo_items
        UNION ALL SELECT 'traducidos',   COUNT(*) FROM tcpo_items WHERE descripcion_es IS NOT NULL
        UNION ALL SELECT 'mandua_materiales', COUNT(*) FROM mandua_materiales
        UNION ALL SELECT 'mandua_mano_obra',  COUNT(*) FROM mandua_mano_obra
        UNION ALL SELECT 'mandua_costeo',     COUNT(*) FROM mandua_costeo
        UNION ALL SELECT 'proyectos',         COUNT(*) FROM proyectos WHERE activo=1
        UNION ALL SELECT 'favoritos',         COUNT(*) FROM favoritos
    """).fetchall()

    df_stats = pd.DataFrame(stats_rows, columns=["Tabla / Métrica", "Registros"])
    st.dataframe(df_stats, use_container_width=False, hide_index=True)

    st.caption(f"DB: `{DB_PATH}`")

    # Edición Mandu'a cargada
    edicion = conn.execute(
        "SELECT fuente_edicion FROM mandua_materiales LIMIT 1"
    ).fetchone()
    if edicion:
        st.caption(f"Edición Mandu'a: {edicion[0]}")

    st.divider()
    st.markdown("""
**TCPO Explorer PY** — v0.1
Catálogo TCPO v15 (VOLARE-15_NOV2018) adaptado para Paraguay.
Precios de referencia Mandu'a — Edición marzo 2026.
[GitHub: tcpo-mandua-mapper](https://github.com/Javier-Duette/tcpo-mandua-mapper)
    """)

    if st.button("🔍 Verificar integridad de DB", key="btn_integridad"):
        issues = []
        n_sin_class = conn.execute(
            "SELECT COUNT(*) FROM tcpo_items WHERE class IS NULL"
        ).fetchone()[0]
        if n_sin_class:
            issues.append(f"tcpo_items sin class: {n_sin_class}")

        n_huerfanos = conn.execute("""
            SELECT COUNT(*) FROM favoritos f
            LEFT JOIN proyectos p ON p.id=f.proyecto_id
            WHERE p.id IS NULL
        """).fetchone()[0]
        if n_huerfanos:
            issues.append(f"Favoritos sin proyecto: {n_huerfanos}")

        n_fk_broken = conn.execute("""
            SELECT COUNT(*) FROM favoritos f
            LEFT JOIN tcpo_items t ON t.id=f.tcpo_item_id
            WHERE t.id IS NULL
        """).fetchone()[0]
        if n_fk_broken:
            issues.append(f"Favoritos con tcpo_item_id inválido: {n_fk_broken}")

        if issues:
            for msg in issues:
                st.warning(msg)
        else:
            st.success("✅ DB íntegra — sin problemas detectados.")
