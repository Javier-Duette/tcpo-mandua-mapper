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
    # Migración: columna de cuarentena
    try:
        conn.execute("ALTER TABLE tcpo_items ADD COLUMN en_revision INTEGER DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    # Migración: marcador de ítem personalizado (creado por el usuario)
    try:
        conn.execute("ALTER TABLE tcpo_items ADD COLUMN es_custom INTEGER DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    # Migración: tabla de composición para ítems PY personalizados
    conn.execute("""
        CREATE TABLE IF NOT EXISTS item_composicion (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER NOT NULL,
            child_id  INTEGER NOT NULL,
            coef      REAL    NOT NULL,
            orden     INTEGER DEFAULT 0,
            FOREIGN KEY (parent_id) REFERENCES tcpo_items(id) ON DELETE CASCADE,
            FOREIGN KEY (child_id)  REFERENCES tcpo_items(id),
            UNIQUE (parent_id, child_id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_item_comp_parent ON item_composicion(parent_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_item_comp_child  ON item_composicion(child_id)")
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _build_where(filtros: dict, proyecto_id: int | None = None) -> tuple[str, list]:
    """Construye cláusula WHERE y lista de parámetros para get_partidas."""
    conds:  list[str] = [
        "t.class IS NOT NULL",
        # Deduplicar: servicios (SER.*) → solo instancia raíz (coef=1.0)
        #             insumos (MAT./M.O./etc.) → solo primera aparición por código
        "(CASE WHEN t.class LIKE 'SER.%' THEN t.coef = 1.0 "
        "      ELSE t.id = (SELECT MIN(id) FROM tcpo_items WHERE codigo = t.codigo) END)",
    ]
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
        q    = f"%{filtros['busqueda']}%"
        modo = filtros.get("busqueda_modo", "descripcion")
        if modo == "codigo":
            conds.append("t.codigo LIKE ?")
            params.append(q)
        elif modo == "ambos":
            conds.append("(t.codigo LIKE ? OR t.descripcion_pt LIKE ? OR t.descripcion_es LIKE ?)")
            params.extend([q, q, q])
        else:   # descripcion (default)
            conds.append("(t.descripcion_pt LIKE ? OR t.descripcion_es LIKE ?)")
            params.extend([q, q])

    if filtros.get("solo_traducidos"):
        conds.append("t.descripcion_es IS NOT NULL")

    if filtros.get("solo_revision"):
        conds.append("t.en_revision = 1")

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
               t.en_revision,
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
    """Retorna los componentes de un servicio.

    Para servicios TCPO originales: usa la estructura flat-secuencial
    (filas entre el id raíz y el próximo SER.* coef=1.0).

    Para servicios personalizados (es_custom=1): usa la tabla relacional
    item_composicion (más flexible, sin restricciones de orden de id).
    """
    conn = get_conn()
    row  = conn.execute(
        "SELECT id, class, es_custom FROM tcpo_items WHERE id=?", (tcpo_item_id,),
    ).fetchone()
    if row is None:
        return pd.DataFrame()

    es_custom = bool(row["es_custom"])
    es_serv   = (row["class"] or "").startswith("SER.")

    # --- Servicio personalizado: composición relacional ---
    if es_custom and es_serv:
        return pd.read_sql_query("""
            SELECT
                t.id                                                  AS id,
                t.codigo                                              AS codigo,
                t.class                                               AS class,
                t.descripcion_pt                                      AS descripcion_pt,
                t.descripcion_es                                      AS descripcion_es,
                t.unidad                                              AS unidad,
                ic.coef                                               AS coef,
                t.precio_brl                                          AS precio_brl,
                (ic.coef * COALESCE(t.precio_brl, 0))                 AS precio_total_brl,
                t.precio_gs                                           AS precio_gs,
                (ic.coef * COALESCE(t.precio_gs, 0))                  AS precio_total_gs,
                t.precio_gs_fuente                                    AS precio_gs_fuente
            FROM item_composicion ic
            JOIN tcpo_items t ON t.id = ic.child_id
            WHERE ic.parent_id = ?
            ORDER BY ic.orden, ic.id
        """, conn, params=(tcpo_item_id,))

    # --- Servicio TCPO original: estructura flat-secuencial ---
    base_id = row["id"]
    return pd.read_sql_query("""
        SELECT id, codigo, class, descripcion_pt, descripcion_es,
               unidad, coef, precio_brl, precio_total_brl,
               precio_gs, precio_total_gs, precio_gs_fuente
        FROM tcpo_items
        WHERE id > ?
          AND class IS NOT NULL
          AND id < (
              SELECT COALESCE(MIN(id), 2147483647)
              FROM tcpo_items
              WHERE id > ? AND class LIKE 'SER.%' AND coef = 1.0
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
            t.precio_gs, t.precio_total_gs,
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
# Precios TCPO — edición y cascade
# ---------------------------------------------------------------------------

def get_insumos_primarios_unicos() -> pd.DataFrame:
    """Un registro por código de insumo primario con su precio BRL y GS actual."""
    conn = get_conn()
    return pd.read_sql_query("""
        SELECT
            t.codigo                                        AS Codigo,
            t.class                                         AS Clase,
            COALESCE(t.descripcion_es, t.descripcion_pt)   AS Descripcion,
            t.unidad                                        AS Unidad,
            t.precio_brl                                    AS Precio_BRL,
            t.precio_gs                                     AS Precio_GS,
            t.precio_gs_fuente                              AS Fuente,
            c.cnt                                           AS Usos
        FROM tcpo_items t
        JOIN (
            SELECT codigo, MIN(id) AS min_id, COUNT(*) AS cnt
            FROM tcpo_items
            WHERE class IN ('MAT.', 'M.O.', 'EQ.AQ.', 'SER.MO', 'EQ.LOC')
            GROUP BY codigo
        ) c ON t.id = c.min_id
        ORDER BY t.class, t.codigo
    """, conn)


def actualizar_precio_insumo_gs(codigo: str, precio_gs: float, fuente: str = "") -> None:
    """Actualiza precio_gs y su fuente en todas las filas con ese código."""
    conn = get_conn()
    conn.execute(
        "UPDATE tcpo_items SET precio_gs=?, precio_gs_fuente=? WHERE codigo=?",
        (precio_gs, fuente or None, codigo),
    )
    conn.commit()


def _calcular_totales_columna(conn, col_precio: str, col_total: str) -> tuple[int, list, int, list]:
    """Recorre la tabla y recalcula totales para una columna de precio (BRL o GS)."""

    # Paso 1: total = coef × precio para no-servicios-raíz
    c1 = conn.execute(f"""
        UPDATE tcpo_items
        SET {col_total} = ROUND(coef * {col_precio}, 2)
        WHERE NOT (class = 'SER.CG' AND coef = 1.0)
          AND {col_precio} IS NOT NULL
    """).rowcount

    # Paso 2: precio de servicios raíz = Σ totales de sus componentes
    rows = conn.execute(
        f"SELECT id, class, coef, {col_total} FROM tcpo_items "
        "WHERE class IS NOT NULL ORDER BY id"
    ).fetchall()

    srv_updates: list[tuple] = []
    srv_id, running = None, 0.0
    for id_, class_, coef, total in rows:
        if class_ == "SER.CG" and coef == 1.0:
            if srv_id is not None:
                srv_updates.append((round(running, 2), round(running, 2), srv_id))
            srv_id, running = id_, 0.0
        else:
            running += total or 0.0
    if srv_id is not None:
        srv_updates.append((round(running, 2), round(running, 2), srv_id))

    conn.executemany(
        f"UPDATE tcpo_items SET {col_precio}=?, {col_total}=? WHERE id=?", srv_updates
    )

    # Paso 3: sub-servicios (SER.CG coef≠1) → recalcular total con precio actualizado
    c3 = conn.execute(f"""
        UPDATE tcpo_items
        SET {col_total} = ROUND(coef * {col_precio}, 2)
        WHERE class = 'SER.CG' AND coef != 1.0
          AND {col_precio} IS NOT NULL
    """).rowcount

    # Paso 4: segunda pasada servicios raíz (anidamiento)
    rows2 = conn.execute(
        f"SELECT id, class, coef, {col_total} FROM tcpo_items "
        "WHERE class IS NOT NULL ORDER BY id"
    ).fetchall()
    srv_updates2: list[tuple] = []
    srv_id, running = None, 0.0
    for id_, class_, coef, total in rows2:
        if class_ == "SER.CG" and coef == 1.0:
            if srv_id is not None:
                srv_updates2.append((round(running, 2), round(running, 2), srv_id))
            srv_id, running = id_, 0.0
        else:
            running += total or 0.0
    if srv_id is not None:
        srv_updates2.append((round(running, 2), round(running, 2), srv_id))
    conn.executemany(
        f"UPDATE tcpo_items SET {col_precio}=?, {col_total}=? WHERE id=?", srv_updates2
    )

    # Paso 5: servicios personalizados (composición relacional via item_composicion)
    # Se ejecuta dos veces para manejar servicios custom anidados.
    for _ in range(2):
        rows_custom = conn.execute(f"""
            SELECT t.id,
                   COALESCE(SUM(ic.coef * COALESCE(child.{col_precio}, 0)), 0) AS total
            FROM tcpo_items t
            LEFT JOIN item_composicion ic ON ic.parent_id = t.id
            LEFT JOIN tcpo_items     child ON child.id = ic.child_id
            WHERE t.es_custom = 1
              AND t.class LIKE 'SER.%'
              AND t.coef = 1.0
            GROUP BY t.id
        """).fetchall()
        for id_, total in rows_custom:
            conn.execute(
                f"UPDATE tcpo_items SET {col_precio}=?, {col_total}=? WHERE id=?",
                (round(total or 0, 2), round(total or 0, 2), id_),
            )

    return c1, srv_updates, c3, srv_updates2


def recalcular_precios_cascade(moneda: str = "gs") -> dict:
    """Recalcula la cadena completa de precios en GS (o BRL si moneda='brl')."""
    conn = get_conn()
    if moneda == "brl":
        c1, u2, c3, u4 = _calcular_totales_columna(conn, "precio_brl", "precio_total_brl")
    else:
        c1, u2, c3, u4 = _calcular_totales_columna(conn, "precio_gs",  "precio_total_gs")
    conn.commit()
    return {"insumos": c1, "servicios_p1": len(u2), "subservicios": c3, "servicios_p2": len(u4)}


# ---------------------------------------------------------------------------
# Precios Mandu'a
# ---------------------------------------------------------------------------

def get_mandua_precios(tipo: str) -> pd.DataFrame:
    """tipo: 'materiales' | 'mano_obra'"""
    conn  = get_conn()
    tabla = "mandua_materiales" if tipo == "materiales" else "mandua_mano_obra"
    return pd.read_sql_query(
        f"SELECT id, seccion, descripcion, unidad, precio_gs FROM {tabla} ORDER BY seccion, descripcion",
        conn,
    )


def actualizar_precio_mandua(tipo: str, item_id: int, precio_gs: float) -> None:
    """Actualiza el precio_gs de un ítem Mandu'a."""
    conn  = get_conn()
    tabla = "mandua_materiales" if tipo == "materiales" else "mandua_mano_obra"
    conn.execute(f"UPDATE {tabla} SET precio_gs=? WHERE id=?", (precio_gs, item_id))
    conn.commit()


# ---------------------------------------------------------------------------
# Notas
# ---------------------------------------------------------------------------

def toggle_revision(tcpo_item_id: int) -> bool:
    """Alterna el flag en_revision. Retorna el nuevo estado (True = en revisión)."""
    conn = get_conn()
    actual = conn.execute(
        "SELECT en_revision FROM tcpo_items WHERE id=?", (tcpo_item_id,)
    ).fetchone()
    nuevo = 0 if (actual and actual["en_revision"]) else 1
    conn.execute("UPDATE tcpo_items SET en_revision=? WHERE id=?", (nuevo, tcpo_item_id))
    conn.commit()
    return bool(nuevo)


def get_count_revision() -> int:
    conn = get_conn()
    return conn.execute(
        "SELECT COUNT(*) FROM tcpo_items WHERE en_revision=1"
    ).fetchone()[0]


def actualizar_descripcion_es(tcpo_item_id: int, descripcion_es: str) -> None:
    conn = get_conn()
    conn.execute(
        "UPDATE tcpo_items SET descripcion_es=? WHERE id=?",
        (descripcion_es.strip() or None, tcpo_item_id),
    )
    conn.commit()


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
    return pd.read_sql_query("""
        SELECT g.id, g.termino_pt, g.termino_es, g.categoria, g.notas,
          (SELECT COUNT(DISTINCT t.id) FROM tcpo_items t
           WHERE t.descripcion_pt LIKE '%' || g.termino_pt || '%') AS usos
        FROM glosario_terminos g ORDER BY g.termino_pt
    """, conn)


def eliminar_glosario_termino(termino_pt: str) -> None:
    conn = get_conn()
    conn.execute("DELETE FROM glosario_terminos WHERE termino_pt=?", (termino_pt,))
    conn.commit()


def upsert_glosario_termino(termino_pt: str, termino_es: str,
                             categoria: str = "", notas: str = "") -> None:
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO glosario_terminos (termino_pt, termino_es, categoria, notas) "
        "VALUES (?,?,?,?)",
        (termino_pt, termino_es, categoria or None, notas or None),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Ítems personalizados (PY) — creación, listado y borrado
# ---------------------------------------------------------------------------

# Mapeo clase → sufijo del código (siguiendo la convención TCPO observada)
_CLASE_SUFIJO = {
    "SER.CG": "SER",
    "SER.MO": "SET",
    "MAT.":   "MAT",
    "M.O.":   "MOD",
    "EQ.LOC": "EQL",
    "EMPRE":  "MOE",
}

# Clases válidas para creación
CLASES_HOJA    = ("MAT.", "M.O.", "EQ.LOC", "EMPRE")
CLASES_SERVICIO = ("SER.CG", "SER.MO")


def _cap_num(capitulo: str | None) -> str:
    """Extrae los primeros dos dígitos del nombre del capítulo. Default: '99'."""
    import re
    if not capitulo:
        return "99"
    m = re.match(r"^\s*(\d{1,2})", capitulo)
    return m.group(1).zfill(2) if m else "99"


def codigo_existe(codigo: str) -> bool:
    """True si ya hay al menos una fila con ese código."""
    conn = get_conn()
    return conn.execute(
        "SELECT 1 FROM tcpo_items WHERE codigo=? LIMIT 1", (codigo,)
    ).fetchone() is not None


def siguiente_codigo_custom(clase: str, capitulo: str | None) -> str:
    """Genera el siguiente código disponible: PY.{cc}.{NNNNNN}.{suf}.

    Auto-incrementa de 5 en 5 dentro del mismo (capítulo, clase).
    """
    suf      = _CLASE_SUFIJO.get(clase, "CUS")
    cap      = _cap_num(capitulo)
    prefijo  = f"PY.{cap}."
    sufijo_p = f".{suf}"

    conn = get_conn()
    row  = conn.execute(
        "SELECT codigo FROM tcpo_items "
        "WHERE codigo LIKE ? AND codigo LIKE ? "
        "ORDER BY codigo DESC LIMIT 1",
        (f"{prefijo}%", f"%{sufijo_p}"),
    ).fetchone()

    if row:
        try:
            num = int(row["codigo"].split(".")[2])
            nuevo = num + 5
        except (IndexError, ValueError):
            nuevo = 5
    else:
        nuevo = 5

    return f"{prefijo}{nuevo:06d}{sufijo_p}"


def crear_item_hoja(
    codigo:        str,
    clase:         str,
    descripcion_es: str,
    unidad:        str,
    precio_gs:     float,
    fuente:        str = "",
    capitulo:      str | None = None,
    subcapitulo:   str | None = None,
    descripcion_pt: str = "",
) -> int:
    """Crea un ítem hoja (MAT./M.O./EQ.LOC/EMPRE).

    Inserta una sola fila con coef=1.0, es_custom=1.
    Retorna el id del ítem creado.
    """
    if clase not in CLASES_HOJA:
        raise ValueError(f"Clase inválida para hoja: {clase}. Usá: {', '.join(CLASES_HOJA)}")
    if not descripcion_es.strip():
        raise ValueError("La descripción es obligatoria.")
    if not unidad.strip():
        raise ValueError("La unidad es obligatoria.")
    if precio_gs <= 0:
        raise ValueError("El precio debe ser mayor a 0.")
    if codigo_existe(codigo):
        raise ValueError(f"El código {codigo} ya existe.")

    conn = get_conn()
    cur  = conn.execute("""
        INSERT INTO tcpo_items (
            codigo, class, descripcion_pt, descripcion_es, unidad, coef,
            precio_gs, precio_total_gs, precio_gs_fuente,
            capitulo, subcapitulo, es_custom
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,1)
    """, (
        codigo, clase,
        (descripcion_pt or descripcion_es).strip(),
        descripcion_es.strip(),
        unidad.strip(), 1.0,
        float(precio_gs), float(precio_gs),
        fuente.strip() or None,
        capitulo or None, subcapitulo or None,
    ))
    conn.commit()
    return cur.lastrowid


def _master_id_de_codigo(codigo: str) -> int | None:
    """Devuelve el id 'canónico' para un código:
    - SER.* con coef=1.0 (definición raíz) si existe
    - sino, MIN(id) (cualquier ocurrencia para hojas)
    """
    conn = get_conn()
    row = conn.execute(
        "SELECT id FROM tcpo_items "
        "WHERE codigo=? AND class LIKE 'SER.%' AND coef=1.0 "
        "ORDER BY id LIMIT 1",
        (codigo,),
    ).fetchone()
    if row:
        return row["id"]
    row = conn.execute("SELECT MIN(id) AS id FROM tcpo_items WHERE codigo=?", (codigo,)).fetchone()
    return row["id"] if row and row["id"] is not None else None


def crear_servicio(
    codigo:        str,
    clase:         str,
    descripcion_es: str,
    unidad:        str,
    componentes:   list[dict],
    capitulo:      str | None = None,
    subcapitulo:   str | None = None,
    descripcion_pt: str = "",
) -> int:
    """Crea un servicio personalizado con composición relacional.

    componentes: lista de dicts {codigo: str, coef: float}.

    Inserta:
    1. Fila raíz en tcpo_items (es_custom=1, coef=1.0)
    2. Filas en item_composicion (parent_id=root, child_id=master del componente, coef, orden)

    Calcula precio_gs como Σ(coef × precio_gs del master).
    Retorna el id de la raíz.
    """
    if clase not in CLASES_SERVICIO:
        raise ValueError(f"Clase inválida para servicio: {clase}. Usá: {', '.join(CLASES_SERVICIO)}")
    if not descripcion_es.strip():
        raise ValueError("La descripción es obligatoria.")
    if not unidad.strip():
        raise ValueError("La unidad es obligatoria.")
    if not componentes:
        raise ValueError("Un servicio requiere al menos un componente.")
    if codigo_existe(codigo):
        raise ValueError(f"El código {codigo} ya existe.")

    conn = get_conn()

    # Validar y resolver master_id de cada componente
    comps_resueltos: list[dict] = []
    codigos_vistos: set[str] = set()
    for c in componentes:
        cod  = c.get("codigo", "").strip()
        coef = float(c.get("coef", 0))
        if not cod or coef <= 0:
            raise ValueError(f"Componente inválido: codigo='{cod}' coef={coef}")
        if cod in codigos_vistos:
            raise ValueError(f"Componente duplicado: {cod}. Sumá los coeficientes en una sola entrada.")
        codigos_vistos.add(cod)

        master_id = _master_id_de_codigo(cod)
        if master_id is None:
            raise ValueError(f"El componente {cod} no existe.")

        master = conn.execute(
            "SELECT precio_gs, precio_brl FROM tcpo_items WHERE id=?", (master_id,),
        ).fetchone()
        comps_resueltos.append({
            "child_id":   master_id,
            "coef":       coef,
            "precio_gs":  master["precio_gs"] or 0,
            "precio_brl": master["precio_brl"] or 0,
        })

    # Calcular precio total
    total_gs  = sum(c["coef"] * c["precio_gs"]  for c in comps_resueltos)
    total_brl = sum(c["coef"] * c["precio_brl"] for c in comps_resueltos)

    # Inserción atómica: raíz en tcpo_items + composición en item_composicion
    try:
        conn.execute("BEGIN")
        cur = conn.execute("""
            INSERT INTO tcpo_items (
                codigo, class, descripcion_pt, descripcion_es, unidad, coef,
                precio_brl, precio_total_brl,
                precio_gs, precio_total_gs,
                capitulo, subcapitulo, es_custom
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1)
        """, (
            codigo, clase,
            (descripcion_pt or descripcion_es).strip(),
            descripcion_es.strip(),
            unidad.strip(), 1.0,
            float(total_brl) if total_brl else None,
            float(total_brl) if total_brl else None,
            float(total_gs)  if total_gs  else None,
            float(total_gs)  if total_gs  else None,
            capitulo or None, subcapitulo or None,
        ))
        root_id = cur.lastrowid

        for orden, c in enumerate(comps_resueltos):
            conn.execute("""
                INSERT INTO item_composicion (parent_id, child_id, coef, orden)
                VALUES (?, ?, ?, ?)
            """, (root_id, c["child_id"], c["coef"], orden))

        conn.commit()
        return root_id
    except Exception:
        conn.rollback()
        raise


def actualizar_item_hoja_custom(
    item_id: int,
    descripcion_es: str | None = None,
    descripcion_pt: str | None = None,
    unidad: str | None = None,
    capitulo: str | None = None,
    subcapitulo: str | None = None,
    precio_gs: float | None = None,
    fuente: str | None = None,
) -> dict:
    """Actualiza los campos de un ítem hoja personalizado.
    Solo modifica los campos pasados (no None). Cambiar precio_gs propaga vía cascade.
    """
    conn = get_conn()
    item = conn.execute(
        "SELECT id, codigo, class, es_custom FROM tcpo_items WHERE id=?", (item_id,),
    ).fetchone()
    if not item:
        return {"ok": False, "msg": "Ítem no encontrado."}
    if not item["es_custom"]:
        return {"ok": False, "msg": "Solo se pueden editar ítems personalizados (PY)."}
    if (item["class"] or "").startswith("SER."):
        return {"ok": False, "msg": "Usá actualizar_servicio_custom para servicios."}

    sets:   list[str] = []
    params: list = []
    if descripcion_es is not None:
        sets.append("descripcion_es=?"); params.append(descripcion_es.strip() or None)
    if descripcion_pt is not None:
        sets.append("descripcion_pt=?"); params.append(descripcion_pt.strip() or None)
    if unidad is not None:
        sets.append("unidad=?");        params.append(unidad.strip() or None)
    if capitulo is not None:
        sets.append("capitulo=?");      params.append(capitulo.strip() or None)
    if subcapitulo is not None:
        sets.append("subcapitulo=?");   params.append(subcapitulo.strip() or None)
    if precio_gs is not None:
        sets.append("precio_gs=?");        params.append(float(precio_gs))
        sets.append("precio_total_gs=?");  params.append(float(precio_gs))  # coef=1.0
    if fuente is not None:
        sets.append("precio_gs_fuente=?"); params.append(fuente.strip() or None)

    if not sets:
        return {"ok": True, "msg": "Sin cambios."}

    params.append(item_id)
    conn.execute(f"UPDATE tcpo_items SET {', '.join(sets)} WHERE id=?", params)
    conn.commit()

    # Si cambió el precio, propagar vía cascade (recalcula totales de servicios que usen este ítem)
    if precio_gs is not None:
        recalcular_precios_cascade(moneda="gs")

    return {"ok": True, "msg": "Ítem actualizado."}


def actualizar_servicio_custom(
    servicio_id: int,
    descripcion_es: str | None = None,
    descripcion_pt: str | None = None,
    unidad: str | None = None,
    capitulo: str | None = None,
    subcapitulo: str | None = None,
    componentes: list[dict] | None = None,
) -> dict:
    """Actualiza un servicio custom (metadata y/o composición).

    Si componentes es None, no toca la composición.
    Si componentes es una lista, REEMPLAZA la composición completa.
    """
    conn = get_conn()
    item = conn.execute(
        "SELECT id, codigo, class, es_custom FROM tcpo_items WHERE id=?", (servicio_id,),
    ).fetchone()
    if not item:
        return {"ok": False, "msg": "Servicio no encontrado."}
    if not item["es_custom"]:
        return {"ok": False, "msg": "Solo se pueden editar servicios personalizados (PY)."}
    if not (item["class"] or "").startswith("SER."):
        return {"ok": False, "msg": "El ítem no es un servicio."}

    try:
        conn.execute("BEGIN")

        # 1. Actualizar metadata
        sets:   list[str] = []
        params: list = []
        for col, val in [
            ("descripcion_es", descripcion_es),
            ("descripcion_pt", descripcion_pt),
            ("unidad",         unidad),
            ("capitulo",       capitulo),
            ("subcapitulo",    subcapitulo),
        ]:
            if val is not None:
                sets.append(f"{col}=?")
                params.append(val.strip() or None)
        if sets:
            params.append(servicio_id)
            conn.execute(f"UPDATE tcpo_items SET {', '.join(sets)} WHERE id=?", params)

        # 2. Actualizar composición si se pasó
        if componentes is not None:
            if not componentes:
                raise ValueError("El servicio requiere al menos un componente.")

            # Validar componentes
            comps_resueltos: list[dict] = []
            codigos_vistos: set[str] = set()
            for c in componentes:
                cod  = c.get("codigo", "").strip()
                coef = float(c.get("coef", 0))
                if not cod or coef <= 0:
                    raise ValueError(f"Componente inválido: codigo='{cod}' coef={coef}")
                if cod in codigos_vistos:
                    raise ValueError(f"Componente duplicado: {cod}.")
                codigos_vistos.add(cod)

                child_id = _master_id_de_codigo(cod)
                if child_id is None:
                    raise ValueError(f"El componente {cod} no existe.")
                if child_id == servicio_id:
                    raise ValueError("Un servicio no puede contenerse a sí mismo.")

                comps_resueltos.append({"child_id": child_id, "coef": coef})

            # Reemplazar
            conn.execute("DELETE FROM item_composicion WHERE parent_id=?", (servicio_id,))
            for orden, c in enumerate(comps_resueltos):
                conn.execute(
                    "INSERT INTO item_composicion (parent_id, child_id, coef, orden) "
                    "VALUES (?, ?, ?, ?)",
                    (servicio_id, c["child_id"], c["coef"], orden),
                )

        conn.commit()
    except Exception:
        conn.rollback()
        raise

    # Recalcular cascade siempre (el precio del servicio depende de sus componentes)
    recalcular_precios_cascade(moneda="gs")

    return {"ok": True, "msg": "Servicio actualizado."}


def get_componentes_servicio_custom(servicio_id: int) -> pd.DataFrame:
    """Retorna los componentes de un servicio custom desde item_composicion."""
    conn = get_conn()
    return pd.read_sql_query("""
        SELECT
            ic.id            AS comp_id,
            ic.coef          AS coef,
            ic.orden         AS orden,
            t.id             AS child_id,
            t.codigo         AS codigo,
            t.class          AS class,
            COALESCE(t.descripcion_es, t.descripcion_pt) AS descripcion,
            t.unidad         AS unidad,
            t.precio_gs      AS precio_gs,
            (ic.coef * COALESCE(t.precio_gs, 0)) AS subtotal_gs
        FROM item_composicion ic
        JOIN tcpo_items t ON t.id = ic.child_id
        WHERE ic.parent_id = ?
        ORDER BY ic.orden, ic.id
    """, conn, params=(servicio_id,))


def listar_items_custom() -> pd.DataFrame:
    """Retorna los ítems personalizados raíz (no las copias-componente).

    Para servicios: solo la fila raíz (coef=1.0).
    Para hojas: solo la primera ocurrencia del código (única en el caso de hojas custom).
    """
    conn = get_conn()
    return pd.read_sql_query("""
        SELECT id, codigo, class, descripcion_es, descripcion_pt, unidad,
               precio_gs, precio_total_gs, capitulo, subcapitulo
        FROM tcpo_items t
        WHERE es_custom = 1
          AND (
              (class LIKE 'SER.%' AND coef = 1.0)
              OR
              (class NOT LIKE 'SER.%' AND id = (
                  SELECT MIN(id) FROM tcpo_items WHERE codigo = t.codigo
              ))
          )
        ORDER BY class, codigo
    """, conn)


def buscar_para_componente(query: str, limit: int = 30) -> pd.DataFrame:
    """Busca ítems para usarlos como componentes de un nuevo servicio.

    Retorna ítems hoja (MAT., M.O., etc.) y servicios (SER.*) raíz, deduplicados.
    """
    conn = get_conn()
    q = f"%{query}%"
    return pd.read_sql_query("""
        SELECT t.id, t.codigo, t.class, t.unidad,
               COALESCE(t.descripcion_es, t.descripcion_pt) AS descripcion,
               t.precio_gs
        FROM tcpo_items t
        WHERE t.class IS NOT NULL
          AND (t.codigo LIKE ? OR t.descripcion_pt LIKE ? OR t.descripcion_es LIKE ?)
          AND (
              (t.class LIKE 'SER.%' AND t.coef = 1.0)
              OR
              (t.class NOT LIKE 'SER.%' AND t.id = (
                  SELECT MIN(id) FROM tcpo_items WHERE codigo = t.codigo
              ))
          )
        ORDER BY t.class, t.codigo
        LIMIT ?
    """, conn, params=(q, q, q, limit))


def eliminar_item_custom(item_id: int) -> dict:
    """Elimina un ítem personalizado.

    - Hoja: solo si no está siendo usada como componente en algún servicio.
    - Servicio: borra la raíz; ON DELETE CASCADE en item_composicion limpia su composición.

    Retorna {"ok": bool, "msg": str}.
    """
    conn = get_conn()
    item = conn.execute(
        "SELECT id, codigo, class, es_custom FROM tcpo_items WHERE id=?", (item_id,)
    ).fetchone()

    if not item:
        return {"ok": False, "msg": "Ítem no encontrado."}
    if not item["es_custom"]:
        return {"ok": False, "msg": "Solo se pueden eliminar ítems personalizados (PY)."}

    es_serv = (item["class"] or "").startswith("SER.")

    # Verificar referencias: ¿este ítem es componente de algún servicio custom?
    refs = conn.execute(
        "SELECT COUNT(*) FROM item_composicion WHERE child_id=?", (item["id"],),
    ).fetchone()[0]
    if refs > 0 and not es_serv:
        return {
            "ok":  False,
            "msg": f"No se puede eliminar: el ítem se usa como componente en {refs} "
                   f"servicio(s) personalizado(s). Removelo de esos servicios primero."
        }

    # Limpiar referencias en favoritos y notas
    conn.execute("DELETE FROM favoritos      WHERE tcpo_item_id=?", (item["id"],))
    conn.execute("DELETE FROM notas_partida  WHERE tcpo_item_id=?", (item["id"],))

    # Si es servicio, item_composicion (parent_id=item_id) se borra por CASCADE
    conn.execute("DELETE FROM tcpo_items WHERE id=?", (item["id"],))
    conn.commit()

    msg = "Servicio eliminado." if es_serv else "Ítem eliminado."
    return {"ok": True, "msg": msg}


def get_capitulos_distintos() -> list[str]:
    """Lista de capítulos únicos (para el selectbox)."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT capitulo FROM tcpo_items "
        "WHERE capitulo IS NOT NULL ORDER BY capitulo"
    ).fetchall()
    return [r["capitulo"] for r in rows]
