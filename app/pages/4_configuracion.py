"""4_configuracion.py — Traducción adicional, glosario y estado del sistema."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import subprocess
import streamlit as st
import pandas as pd

from app.utils.queries import get_cobertura_por_capitulo, get_glosario, upsert_glosario_termino
from app.utils.formatters import fmt_pct

st.set_page_config(page_title="Configuración — TCPO PY", layout="wide",
                   page_icon="⚙️", initial_sidebar_state="collapsed")

st.title("⚙️ Configuración")

tab_trad, tab_glos, tab_about = st.tabs(
    ["🌐 Traducir capítulos", "📖 Glosario", "ℹ️ Acerca de"]
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
# TAB 2 — Glosario
# ============================================================
with tab_glos:
    st.subheader("Glosario PT → ES Paraguay")

    df_glos = get_glosario()
    st.caption(f"{len(df_glos)} términos cargados.")

    st.dataframe(
        df_glos[["termino_pt", "termino_es", "categoria", "notas"]].rename(columns={
            "termino_pt":  "Término PT",
            "termino_es":  "Término ES",
            "categoria":   "Categoría",
            "notas":       "Notas",
        }),
        use_container_width=True,
        hide_index=True,
        height=300,
    )

    st.divider()
    st.subheader("Agregar / editar término")

    with st.form("form_glosario"):
        c1, c2 = st.columns(2)
        pt       = c1.text_input("Término PT",  key="glos_pt")
        es       = c2.text_input("Término ES",  key="glos_es")
        cat      = st.text_input("Categoría (opcional)", key="glos_cat")
        notas_g  = st.text_input("Notas (opcional)",     key="glos_notas")
        if st.form_submit_button("Guardar término"):
            if pt.strip() and es.strip():
                upsert_glosario_termino(pt.strip(), es.strip(), cat.strip(), notas_g.strip())
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
