"""export.py — Generación de Excel y CSV para exportación de proyectos."""
import io
from datetime import datetime

import pandas as pd


def _subtotal(row) -> float | None:
    qty   = row.get("cantidad_estimada")
    price = row.get("precio_unitario_manual_gs")
    if qty and price:
        return float(qty) * float(price)
    return None


def _preparar_df(df: pd.DataFrame, idioma: str = "ES") -> pd.DataFrame:
    """Agrega columna subtotal y selecciona descripción según idioma."""
    out = df.copy()
    out["subtotal_gs"] = out.apply(_subtotal, axis=1)
    if idioma == "PT":
        out["descripcion"] = out["descripcion_pt"]
    elif idioma == "ambos":
        out["descripcion"] = out.apply(
            lambda r: f"{r.get('descripcion_es','') or ''} / {r.get('descripcion_pt','') or ''}",
            axis=1,
        )
    else:  # ES (default)
        out["descripcion"] = out["descripcion_es"].fillna(out["descripcion_pt"])
    return out


def generar_excel_completo(df: pd.DataFrame, nombre_proyecto: str,
                           idioma: str = "ES") -> bytes:
    """Excel con todas las columnas útiles."""
    out = _preparar_df(df, idioma)

    columnas = [
        ("orden",                     "Orden"),
        ("codigo",                    "Código TCPO"),
        ("class",                     "Clase"),
        ("descripcion",               "Descripción"),
        ("unidad",                    "Unidad"),
        ("cantidad_estimada",         "Cantidad"),
        ("precio_unitario_manual_gs", "Precio Unit. Gs."),
        ("subtotal_gs",               "Subtotal Gs."),
        ("precio_brl",                "Precio Ref. BRL"),
        ("relevancia_py",             "Relevancia PY"),
        ("capitulo",                  "Capítulo"),
        ("subcapitulo",               "Subcapítulo"),
        ("match_mandua",              "Match Mandu'a"),
        ("notas_propias",             "Notas"),
    ]
    cols_ok = [(c, h) for c, h in columnas if c in out.columns]
    exp = out[[c for c, _ in cols_ok]].copy()
    exp.columns = [h for _, h in cols_ok]

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        exp.to_excel(writer, index=False, sheet_name="Presupuesto")
        ws = writer.sheets["Presupuesto"]
        # Ancho automático (simplificado)
        for col in ws.columns:
            max_len = max((len(str(c.value or "")) for c in col), default=10)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 50)
        # Fila de totales
        total_gs = exp["Subtotal Gs."].sum() if "Subtotal Gs." in exp.columns else 0
        row_total = exp.shape[0] + 2
        ws.cell(row=row_total, column=1, value="TOTAL")
        # Buscar columna Subtotal Gs.
        for i, c in enumerate(exp.columns, 1):
            if c == "Subtotal Gs.":
                ws.cell(row=row_total, column=i, value=total_gs)
                break
        # Hoja de metadata
        meta = pd.DataFrame([
            ("Proyecto",        nombre_proyecto),
            ("Exportado",       datetime.now().strftime("%Y-%m-%d %H:%M")),
            ("Partidas",        len(exp)),
            ("Total Gs.",       total_gs),
        ], columns=["Campo", "Valor"])
        meta.to_excel(writer, index=False, sheet_name="Info")
    return buf.getvalue()


def generar_excel_dynamo(df: pd.DataFrame, nombre_proyecto: str,
                         idioma: str = "ES") -> bytes:
    """Excel Dynamo-friendly para mapeo posterior en Revit."""
    out = _preparar_df(df, idioma)
    exp = pd.DataFrame({
        "Familia_Tipo":       "",           # el usuario llena en Revit/Dynamo
        "Descripcion":        out["descripcion"],
        "Unidad":             out.get("unidad", ""),
        "Cantidad":           out.get("cantidad_estimada", ""),
        "Precio_Unitario_Gs": out.get("precio_unitario_manual_gs", ""),
        "Subtotal_Gs":        out["subtotal_gs"],
        "Codigo_TCPO":        out.get("codigo", ""),
        "Match_Mandua":       out.get("match_mandua", ""),
    })
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        exp.to_excel(writer, index=False, sheet_name=nombre_proyecto[:30])
    return buf.getvalue()


def generar_csv(df: pd.DataFrame, idioma: str = "ES") -> str:
    out = _preparar_df(df, idioma)
    return out.to_csv(index=False)
