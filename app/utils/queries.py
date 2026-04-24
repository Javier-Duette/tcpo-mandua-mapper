"""queries.py — Todas las consultas SQL como funciones puras.

Usan una conexión SQLite compartida via st.cache_resource.
Las funciones de escritura llaman conn.commit() explícitamente.
"""
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

ROOT    = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "precios.db"

# ---------------------------------------------------------------------------
# Conexión
# ---------------------------------------------------------------------------

@st.cache_resource
def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _build_where(filtros: dict, proyecto_id: int | None = None) -> tuple[str, list]:
    """Construye cláusula WHERE y lista de parámetros para get_partidas."""
    conds:  list[str] = ["t.class IS NOT NULL"]
    params: list[Any] = []

    if filtros.get("capitulos"):
        phs = ",".join("?" for _ in filtros["capitulos"])
        conds.append(f"t.capitulo IN ({phs})")
        params.extend(filtros["capitulos"])

    if filtros.get("subcapitulos"):
        phs = ",".join("?" for _ in filtros["subcapitulos"])
        conds.append(f"t.subcapitulo IN ({phs})")
        params.extend(filtros["subcapitulos"])

    # clases tiene precedencia sobre solo_servicios
    if filtros.get("clases"):
        phs = ",".join("?" for _ in filtros["clases"])
        conds.append(f"t.class IN ({phs})")
        params.extend(filtros["clases"])
    elif filtros.get("solo_servicios", True):
        conds.append("t.class = 'SER.CG'")

    if filtros.get("relevancia"):
        phs = ",".join("?" for _ in filtros["relevancia"])
        conds.append(f"t.relevancia_py IN ({phs})")
        params.extend(filtros["relevancia"])

    if filtros.get("busqueda"):
        q = f"%{filtros['busqueda']}%"
        conds.append("(t.descripcion_pt LIKE ? OR t.descripcion_es LIKE ?)")
        params.extend([q, q])

    if filtros.get("solo_traducidos"):
        conds.append("t.descripcion_es IS NOT NULL")

    if filtros.get("excluir_no_aplica"):
        conds.append("(t.relevancia_py IS NULL OR t.relevancia_py != 'no_aplica')")

    return " AND ".join(conds), params


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def get_dashboard_stats() -> dict:
    conn = get_conn()
    total      = conn.execute("SELECT COUNT(*) FROM tcpo_items WHERE class IS NOT NULL").fetchone()[0]
    traducidos = conn.execute("SELECT COUNT(*) FROM tcpo_items WHERE descripcion_es IS NOT NULL AND class IS NOT NULL").fetchone()[0]
    rows_rel   = conn.execute("""
        SELECT relevancia_py, COUNT(*) as n FROM tcpo_items
        WHERE class IS NOT NULL GROUP BY relevancia_py
    """).fetchall()
    dist_rel   = {r["relevancia_py"] or "sin_clasificar": r["n"] for r in rows_rel}

    proyectos  = conn.execute("SELECT COUNT(*) FROM proyectos WHERE activo=1").fetchone()[0]
    favoritos  = conn.execute("SELECT COUNT(*) FROM favoritos").fetchone()[0]
    return {
        "total":        total,
        "traducidos":   traducidos,
        "pct_trad":     round(100 * traducidos / max(total, 1)),
        "dist_rel":     dist_rel,
        "n_proyectos":  proyectos,
        "n_favoritos":  favoritos,
    }


# ---------------------------------------------------------------------------
# Capítulos
# ---------------------------------------------------------------------------

def get_capitulos_con_conteo() -> pd.DataFrame:
    conn = get_conn()
    return pd.read_sql_query("""
        SELECT
            capitulo,
            COUNT(*) AS total,
            SUM(CASE WHEN class='SER.CG' THEN 1 ELSE 0 END)          AS n_servicios,
            SUM(CASE WHEN relevancia_py='alta' THEN 1 ELSE 0 END)     AS n_alta,
            SUM(CASE WHEN descripcion_es IS NOT NULL THEN 1 ELSE 0 END) AS n_traducidos
        FROM tcpo_items
        WHERE class IS NOT NULL
        GROUP BY capitulo
        ORDER BY capitulo
    """, conn)


def get_subcapitulos(capitulos: list[str]) -> list[str]:
    if not capitulos:
        return []
    conn  = get_conn()
    phs   = ",".join("?" for _ in capitulos)
    rows  = conn.execute(
        f"SELECT DISTINCT subcapitulo FROM tcpo_items "
        f"WHERE capitulo IN ({phs}) AND subcapitulo IS NOT NULL ORDER BY subcapitulo",
        capitulos,
    ).fetchall()
    return [r["subcapitulo"] for r in rows]


# ---------------------------------------------------------------------------
# Partidas (explorador)
# ---------------------------------------------------------------------------

def get_partidas(filtros: dict, limit: int = 50, offset: int = 0,
                 proyecto_id: int | None = None) -> pd.DataFrame:
    conn         = get_conn()
    where, params = _build_where(filtros)

    fav_join = ""
    fav_col  = "0 AS es_favorito"
    if proyecto_id is not None:
        fav_join = "LEFT JOIN favoritos f ON f.tcpo_item_id=t.id AND f.proyecto_id=?"
        fav_col  = "CASE WHEN f.id IS NOT NULL THEN 1 ELSE 0 END AS es_favorito"
        params   = [proyecto_id] + params   # proyecto_id antes del WHERE

    sql = f"""
        SELECT t.id, t.codigo, t.class, t.descripcion_pt, t.descripcion_es,
               t.unidad, t.coef, t.precio_brl, t.precio_total_brl,
               t.capitulo, t.subcapitulo,
               t.relevancia_py, t.relevancia_justificacion,
               {fav_col}
        FROM tcpo_items t
        {fav_join}
        WHERE {where}
        ORDER BY t.capitulo, t.codigo
        LIMIT ? OFFSET ?
    """
    params = params + [limit, offset]
    return pd.read_sql_query(sql, conn, params=params)


def get_total_partidas(filtros: dict) -> int:
    conn          = get_conn()
    where, params = _build_where(filtros)
    row = conn.execute(
        f"SELECT COUNT(*) FROM tcpo_items t WHERE {where}", params
    ).fetchone()
    return row[0]


def get_detalle_partida(tcpo_item_id: int) -> dict | None:
    conn = get_conn()
    row  = conn.execute("""
        SELECT t.*, n.nota AS nota_propia
        FROM tcpo_items t
        LEFT JOIN notas_partida n ON n.tcpo_item_id = t.id
        WHERE t.id = ?
    """, (tcpo_item_id,)).fetchone()
    return dict(row) if row else None


def get_insumos_de_partida(tcpo_item_id: int) -> pd.DataFrame:
    """Retorna los insumos (MAT./M.O.) que componen una partida SER.CG."""
    conn = get_conn()
    row  = conn.execute("SELECT id FROM tcpo_items WHERE id=?", (tcpo_item_id,)).fetchone()
    if row is None:
        return pd.DataFrame()
    base_id = row["id"]
    return pd.read_sql_query("""
        SELECT id, codigo, class, descripcion_pt, descripcion_es,
               unidad, coef, precio_brl, precio_total_brl
        FROM tcpo_items
        WHERE id > ?
          AND class IN ('MAT.', 'M.O.', 'EQ.AQ.', 'DIVER', 'SER.CH')
          AND id < (
              SELECT COALESCE(MIN(id), 2147483647)
              FROM tcpo_items WHERE id > ? AND class = 'SER.CG'
          )
        ORDER BY id
    """, conn, params=(base_id, base_id))


# ---------------------------------------------------------------------------
# Proyectos
# ---------------------------------------------------------------------------

def get_proyectos() -> pd.DataFrame:
    conn = get_conn()
    return pd.read_sql_query("""
        SELECT p.id, p.nombre, p.descripcion, p.fecha_creacion,
               COUNT(f.id) AS n_favoritos
        FROM proyectos p
        LEFT JOIN favoritos f ON f.proyecto_id = p.id
        WHERE p.activo = 1
        GROUP BY p.id
        ORDER BY p.fecha_creacion DESC
    """, conn)


def crear_proyecto(nombre: str, descripcion: str = "") -> int:
    conn = get_conn()
    cur  = conn.execute(
        "INSERT INTO proyectos (nombre, descripcion) VALUES (?,?)",
        (nombre, descripcion or None),
    )
    conn.commit()
    return cur.lastrowid


def actualizar_proyecto(proyecto_id: int, nombre: str, descripcion: str) -> None:
    conn = get_conn()
    conn.execute(
        "UPDATE proyectos SET nombre=?, descripcion=?, fecha_modificacion=CURRENT_TIMESTAMP "
        "WHERE id=?",
        (nombre, descripcion or None, proyecto_id),
    )
    conn.commit()


def eliminar_proyecto(proyecto_id: int) -> None:
    conn = get_conn()
    conn.execute("UPDATE proyectos SET activo=0 WHERE id=?", (proyecto_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Favoritos
# ---------------------------------------------------------------------------

def get_favoritos_con_detalle(proyecto_id: int) -> pd.DataFrame:
    conn = get_conn()
    return pd.read_sql_query("""
        SELECT
            f.id AS fav_id, f.orden, f.cantidad_estimada,
            f.precio_unitario_manual_gs, f.notas_propias,
            f.mandua_tipo, f.mandua_id,
            t.id AS tcpo_id, t.codigo, t.class,
            t.descripcion_es, t.descripcion_pt,
            t.unidad, t.coef, t.precio_brl,
            t.capitulo, t.subcapitulo, t.relevancia_py,
            CASE f.mandua_tipo
                WHEN 'material'   THEN (SELECT descripcion FROM mandua_materiales WHERE id=f.mandua_id)
                WHEN 'mano_obra'  THEN (SELECT descripcion FROM mandua_mano_obra   WHERE id=f.mandua_id)
            END AS match_mandua
        FROM favoritos f
        JOIN tcpo_items t ON t.id = f.tcpo_item_id
        WHERE f.proyecto_id = ?
        ORDER BY COALESCE(f.orden, f.id)
    """, conn, params=(proyecto_id,))


def esta_en_favoritos(proyecto_id: int, tcpo_item_id: int) -> bool:
    conn = get_conn()
    r = conn.execute(
        "SELECT id FROM favoritos WHERE proyecto_id=? AND tcpo_item_id=?",
        (proyecto_id, tcpo_item_id),
    ).fetchone()
    return r is not None


def agregar_favorito(proyecto_id: int, tcpo_item_id: int) -> int | None:
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO favoritos (proyecto_id, tcpo_item_id) VALUES (?,?)",
            (proyecto_id, tcpo_item_id),
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return None   # ya existía (UNIQUE)


def eliminar_favorito(fav_id: int) -> None:
    conn = get_conn()
    conn.execute("DELETE FROM favoritos WHERE id=?", (fav_id,))
    conn.commit()


def actualizar_favorito(fav_id: int, campos: dict) -> None:
    if not campos:
        return
    conn    = get_conn()
    setters = ", ".join(f"{k}=?" for k in campos)
    vals    = list(campos.values()) + [fav_id]
    conn.execute(f"UPDATE favoritos SET {setters} WHERE id=?", vals)
    conn.commit()


def reordenar_favoritos(fav_ids: list[int]) -> None:
    """Asigna orden=0,1,2... según el orden de la lista."""
    conn = get_conn()
    conn.executemany("UPDATE favoritos SET orden=? WHERE id=?",
                     [(i, fid) for i, fid in enumerate(fav_ids)])
    conn.commit()


# ---------------------------------------------------------------------------
# Búsqueda Mandu'a
# ---------------------------------------------------------------------------

def buscar_mandua(tipo: str, query_str: str, limit: int = 30) -> pd.DataFrame:
    """tipo: 'material' | 'mano_obra' | 'any'"""
    conn = get_conn()
    q    = f"%{query_str}%"
    if tipo == "material":
        return pd.read_sql_query(
            "SELECT id, descripcion, unidad, precio_gs, seccion FROM mandua_materiales "
            "WHERE descripcion LIKE ? ORDER BY descripcion LIMIT ?",
            conn, params=(q, limit),
        )
    if tipo == "mano_obra":
        return pd.read_sql_query(
            "SELECT id, descripcion, unidad, precio_gs, seccion FROM mandua_mano_obra "
            "WHERE descripcion LIKE ? ORDER BY descripcion LIMIT ?",
            conn, params=(q, limit),
        )
    # any: union
    df_m = pd.read_sql_query(
        "SELECT id, 'material' AS tipo, descripcion, unidad, precio_gs FROM mandua_materiales "
        "WHERE descripcion LIKE ? LIMIT ?", conn, params=(q, limit // 2),
    )
    df_o = pd.read_sql_query(
        "SELECT id, 'mano_obra' AS tipo, descripcion, unidad, precio_gs FROM mandua_mano_obra "
        "WHERE descripcion LIKE ? LIMIT ?", conn, params=(q, limit // 2),
    )
    return pd.concat([df_m, df_o], ignore_index=True)


# ---------------------------------------------------------------------------
# Notas
# ---------------------------------------------------------------------------

def get_nota_partida(tcpo_item_id: int) -> str:
    conn = get_conn()
    row  = conn.execute(
        "SELECT nota FROM notas_partida WHERE tcpo_item_id=?", (tcpo_item_id,)
    ).fetchone()
    return row["nota"] if row else ""


def guardar_nota_partida(tcpo_item_id: int, nota: str) -> None:
    conn = get_conn()
    if nota.strip():
        conn.execute(
            "INSERT OR REPLACE INTO notas_partida (tcpo_item_id, nota, fecha_modificacion) "
            "VALUES (?,?,CURRENT_TIMESTAMP)",
            (tcpo_item_id, nota.strip()),
        )
    else:
        conn.execute("DELETE FROM notas_partida WHERE tcpo_item_id=?", (tcpo_item_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Configuración / stats de traducción por capítulo
# ---------------------------------------------------------------------------

def get_cobertura_por_capitulo() -> pd.DataFrame:
    conn = get_conn()
    return pd.read_sql_query("""
        SELECT
            capitulo,
            SUBSTR(capitulo, 1, 2)  AS codigo_cap,
            COUNT(*)                AS total,
            SUM(CASE WHEN descripcion_es IS NOT NULL THEN 1 ELSE 0 END) AS traducidos,
            SUM(CASE WHEN relevancia_py != 'sin_clasificar' AND relevancia_py IS NOT NULL
                     THEN 1 ELSE 0 END) AS clasificados,
            SUM(CASE WHEN class = 'SER.CG' THEN 1 ELSE 0 END) AS n_servicios
        FROM tcpo_items
        WHERE class IS NOT NULL
        GROUP BY capitulo
        ORDER BY capitulo
    """, conn)


def get_glosario() -> pd.DataFrame:
    conn = get_conn()
    return pd.read_sql_query(
        "SELECT id, termino_pt, termino_es, categoria, notas FROM glosario_terminos ORDER BY termino_pt",
        conn,
    )


def upsert_glosario_termino(termino_pt: str, termino_es: str,
                             categoria: str = "", notas: str = "") -> None:
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO glosario_terminos (termino_pt, termino_es, categoria, notas) "
        "VALUES (?,?,?,?)",
        (termino_pt, termino_es, categoria or None, notas or None),
    )
    conn.commit()
