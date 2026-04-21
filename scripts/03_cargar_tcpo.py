"""03_cargar_tcpo.py - Carga TCPO 15 a SQLite con jerarquía de capítulos."""
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import openpyxl
from unidecode import unidecode as _unidecode

from src.db import get_connection
from src.config import TCPO_XLSX

SHEET_NAME = "VOLARE-15_NOV2018"
DATA_START_ROW = 10
BATCH_SIZE = 5000


def normalizar_texto(s):
    if not s:
        return None
    s = _unidecode(str(s)).lower()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def _is_plain_int(val):
    """True when val is an integer or a float/string with no decimal part."""
    if val is None:
        return False
    if isinstance(val, int):
        return True
    if isinstance(val, float):
        return val == int(val)
    if isinstance(val, str):
        try:
            int(val.strip())
            return True
        except ValueError:
            return False
    return False


def _to_int(val):
    return int(val) if isinstance(val, int) else int(float(val))


def _safe_float(val):
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f"Abriendo {TCPO_XLSX} ...")
    wb = openpyxl.load_workbook(TCPO_XLSX, read_only=True, data_only=True)
    ws = wb[SHEET_NAME]

    conn = get_connection()
    conn.execute("DELETE FROM tcpo_items")
    conn.commit()

    capitulo_actual = None
    subcapitulo_actual = None
    batch = []
    total = 0
    class_counts: dict[str, int] = {}

    INSERT_SQL = (
        "INSERT INTO tcpo_items "
        "(codigo, descripcion_pt, descripcion_pt_normalizada, class, unidad, coef, "
        "precio_brl, precio_total_brl, capitulo, subcapitulo, fila_original) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)"
    )

    def flush():
        if batch:
            conn.executemany(INSERT_SQL, batch)
            conn.commit()
            batch.clear()

    for row_idx, row in enumerate(
        ws.iter_rows(min_row=DATA_START_ROW, values_only=True), start=DATA_START_ROW
    ):
        # Pad to 7 columns in case the row is short
        vals = list(row) + [None] * 7
        codigo, desc, cls, unidad, coef, precio, precio_total = vals[:7]

        # Skip fully-empty rows
        if all(v is None for v in vals[:7]):
            continue

        is_chapter = cls is None and _is_plain_int(codigo)
        is_data = cls is not None

        # Skip composition-group markers ("04.103.0") and footer
        if not is_chapter and not is_data:
            continue

        if is_chapter:
            n = _to_int(codigo)
            if n < 100:
                capitulo_actual = str(desc).strip() if desc else str(n)
                subcapitulo_actual = None
            else:
                subcapitulo_actual = str(desc).strip() if desc else str(n)

        codigo_str = str(codigo).strip() if codigo is not None else None
        desc_str = str(desc).strip() if desc is not None else None

        batch.append((
            codigo_str,
            desc_str,
            normalizar_texto(desc_str),
            str(cls).strip() if cls else None,
            str(unidad).strip() if unidad else None,
            _safe_float(coef),
            _safe_float(precio),
            _safe_float(precio_total),
            capitulo_actual,
            subcapitulo_actual,
            row_idx,
        ))

        cls_key = str(cls).strip() if cls else "CAPÍTULO"
        class_counts[cls_key] = class_counts.get(cls_key, 0) + 1
        total += 1

        if len(batch) >= BATCH_SIZE:
            flush()
            print(f"  ... {total:>7} filas insertadas")

    flush()
    wb.close()

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    EXPECTED = 40_477
    delta = abs(total - EXPECTED)

    print(f"\n--- Resumen de carga ---")
    print(f"  Total insertado : {total}")
    print(f"  Total esperado  : ~{EXPECTED}")
    if delta > 500:
        print(f"  WARNING: diferencia de {delta} filas respecto al esperado")
    else:
        print(f"  OK: diferencia de {delta} filas (dentro del margen)")

    print(f"\n--- Conteo por CLASS ---")
    for cls_k, n in sorted(class_counts.items(), key=lambda x: -x[1]):
        flag = ""
        if cls_k == "SER.CG"  and abs(n - 7306) > 200:  flag = "  ← WARNING"
        if cls_k == "MAT."    and abs(n - 16542) > 500:  flag = "  ← WARNING"
        if cls_k == "M.O."    and abs(n - 9173) > 300:   flag = "  ← WARNING"
        print(f"  {cls_k:<12} {n:>7}{flag}")

    # 3 SER.CG samples with their first insumos
    print(f"\n--- 3 partidas SER.CG de muestra ---")
    partidas = conn.execute(
        "SELECT id, codigo, descripcion_pt, unidad, precio_total_brl, fila_original "
        "FROM tcpo_items WHERE class='SER.CG' LIMIT 3"
    ).fetchall()

    for p in partidas:
        next_ser = conn.execute(
            "SELECT fila_original FROM tcpo_items "
            "WHERE class='SER.CG' AND fila_original > ? LIMIT 1",
            (p["fila_original"],),
        ).fetchone()
        limit_row = next_ser["fila_original"] if next_ser else p["fila_original"] + 50

        print(f"\n  [{p['codigo']}] {p['descripcion_pt'][:65]}")
        print(f"  {p['unidad']}  R$ {p['precio_total_brl']:.2f}")
        insumos = conn.execute(
            "SELECT class, descripcion_pt, coef, unidad FROM tcpo_items "
            "WHERE fila_original > ? AND fila_original < ? LIMIT 5",
            (p["fila_original"], limit_row),
        ).fetchall()
        for ins in insumos:
            print(f"    {ins['class']:<8} {ins['coef']:>6}  {ins['unidad']:<4}  {ins['descripcion_pt'][:50]}")

    # Required query
    print(f"\n--- SER.CG por capítulo ---")
    for row in conn.execute(
        "SELECT capitulo, COUNT(*) as total FROM tcpo_items "
        "WHERE class='SER.CG' GROUP BY capitulo ORDER BY capitulo"
    ):
        print(f"  {row['total']:>5}  {row['capitulo']}")

    conn.close()


if __name__ == "__main__":
    main()
