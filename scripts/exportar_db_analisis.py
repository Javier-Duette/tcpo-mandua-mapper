"""exportar_db_analisis.py — Exporta todas las tablas de precios.db a Excel/CSV.

Uso:
  python scripts/exportar_db_analisis.py              # Excel multi-hoja
  python scripts/exportar_db_analisis.py --csv        # CSV por tabla
  python scripts/exportar_db_analisis.py --tabla tcpo_items --csv
"""
import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT    = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "precios.db"
OUT_DIR = ROOT / "exports"


# Consultas optimizadas para análisis (evita cols binarias, agrega columnas útiles)
TABLAS: dict[str, str] = {
    "tcpo_items": """
        SELECT
            id, codigo, class,
            capitulo, subcapitulo,
            descripcion_pt, descripcion_es,
            unidad, coef,
            precio_brl, precio_total_brl,
            relevancia_py, relevancia_justificacion,
            CASE WHEN descripcion_es IS NOT NULL THEN 1 ELSE 0 END AS traducido
        FROM tcpo_items
        ORDER BY capitulo, codigo
    """,
    "mandua_materiales": """
        SELECT id, seccion, descripcion, unidad, precio_gs, fuente_edicion
        FROM mandua_materiales
        ORDER BY seccion, descripcion
    """,
    "mandua_mano_obra": """
        SELECT id, seccion, descripcion, unidad, precio_gs, fuente_edicion
        FROM mandua_mano_obra
        ORDER BY seccion, descripcion
    """,
    "proyectos": """
        SELECT p.id, p.nombre, p.descripcion, p.fecha_creacion,
               COUNT(f.id) AS n_favoritos
        FROM proyectos p
        LEFT JOIN favoritos f ON f.proyecto_id = p.id
        WHERE p.activo = 1
        GROUP BY p.id
    """,
    "favoritos": """
        SELECT f.id, f.proyecto_id, p.nombre AS proyecto,
               t.codigo, t.descripcion_es, t.unidad,
               f.cantidad_estimada,
               f.precio_unitario_manual_gs,
               ROUND(COALESCE(f.cantidad_estimada,0) *
                     COALESCE(f.precio_unitario_manual_gs,0)) AS subtotal_gs,
               f.mandua_tipo, f.notas_propias,
               t.relevancia_py, t.capitulo
        FROM favoritos f
        JOIN tcpo_items t ON t.id = f.tcpo_item_id
        JOIN proyectos p  ON p.id = f.proyecto_id
        ORDER BY p.nombre, f.orden, f.id
    """,
    "resumen_cobertura": """
        SELECT
            capitulo,
            COUNT(*)                                                         AS total,
            SUM(CASE WHEN class='SER.CG' THEN 1 ELSE 0 END)                 AS servicios,
            SUM(CASE WHEN descripcion_es IS NOT NULL THEN 1 ELSE 0 END)     AS traducidos,
            SUM(CASE WHEN relevancia_py='alta'     THEN 1 ELSE 0 END)       AS alta,
            SUM(CASE WHEN relevancia_py='media'    THEN 1 ELSE 0 END)       AS media,
            SUM(CASE WHEN relevancia_py='baja'     THEN 1 ELSE 0 END)       AS baja,
            SUM(CASE WHEN relevancia_py='no_aplica' THEN 1 ELSE 0 END)      AS no_aplica,
            SUM(CASE WHEN descripcion_es IS NOT NULL THEN 1 ELSE 0 END) * 100 /
                MAX(COUNT(*), 1)                                             AS pct_traducido
        FROM tcpo_items
        WHERE class IS NOT NULL
        GROUP BY capitulo
        ORDER BY capitulo
    """,
    "glosario_terminos": """
        SELECT termino_pt, termino_es, categoria, notas FROM glosario_terminos
        ORDER BY termino_pt
    """,
}


def exportar_excel(conn: sqlite3.Connection, out_path: Path) -> None:
    print(f"Exportando Excel -> {out_path}")
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        for nombre, sql in TABLAS.items():
            df = pd.read_sql_query(sql, conn)
            hoja = nombre[:31]          # Excel límite 31 chars
            df.to_excel(writer, sheet_name=hoja, index=False)
            ws = writer.sheets[hoja]
            # Ancho automático
            for col in ws.columns:
                max_w = max((len(str(c.value or "")) for c in col), default=8)
                ws.column_dimensions[col[0].column_letter].width = min(max_w + 2, 60)
            print(f"  {hoja}: {len(df):,} filas")

        # Hoja de metadata
        meta = pd.DataFrame([
            ("Exportado",  datetime.now().strftime("%Y-%m-%d %H:%M")),
            ("DB",         str(DB_PATH)),
            ("Script",     "scripts/exportar_db_analisis.py"),
        ], columns=["Campo", "Valor"])
        meta.to_excel(writer, sheet_name="Info", index=False)
    print(f"OK Excel listo: {out_path}")


def exportar_csv(conn: sqlite3.Connection, out_dir: Path, tabla: str | None) -> None:
    tablas = {tabla: TABLAS[tabla]} if tabla else TABLAS
    out_dir.mkdir(parents=True, exist_ok=True)
    for nombre, sql in tablas.items():
        df   = pd.read_sql_query(sql, conn)
        path = out_dir / f"{nombre}.csv"
        df.to_csv(path, index=False, encoding="utf-8-sig")   # utf-8-sig → Excel abre sin BOM issues
        print(f"  {nombre}.csv: {len(df):,} filas -> {path}")
    print(f"OK CSVs en: {out_dir}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv",    action="store_true", help="Exportar CSV por tabla (default: Excel)")
    parser.add_argument("--tabla",  default=None,        help="Solo esta tabla (requiere --csv)")
    args = parser.parse_args()

    if args.tabla and args.tabla not in TABLAS:
        print(f"ERROR: tabla '{args.tabla}' no existe. Opciones: {', '.join(TABLAS)}")
        sys.exit(1)

    OUT_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    if args.csv:
        exportar_csv(conn, OUT_DIR / "csv", args.tabla)
    else:
        ts  = datetime.now().strftime("%Y%m%d_%H%M")
        out = OUT_DIR / f"tcpo_explorer_py_{ts}.xlsx"
        exportar_excel(conn, out)

    conn.close()


if __name__ == "__main__":
    main()
