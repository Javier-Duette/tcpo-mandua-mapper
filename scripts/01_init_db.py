import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import get_connection

DDL = [
    """
    CREATE TABLE IF NOT EXISTS mandua_materiales (
        id                      INTEGER PRIMARY KEY AUTOINCREMENT,
        descripcion             TEXT NOT NULL,
        descripcion_normalizada TEXT,
        unidad                  TEXT,
        precio_gs               INTEGER,
        seccion                 TEXT,
        subseccion              TEXT,
        fuente_edicion          TEXT,
        fecha_carga             DATE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS mandua_mano_obra (
        id                      INTEGER PRIMARY KEY AUTOINCREMENT,
        descripcion             TEXT NOT NULL,
        descripcion_normalizada TEXT,
        unidad                  TEXT,
        precio_gs               INTEGER,
        seccion                 TEXT,
        subseccion              TEXT,
        fuente_edicion          TEXT,
        fecha_carga             DATE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS mandua_costeo (
        id              INTEGER PRIMARY KEY,
        partida         TEXT,
        seccion         TEXT,
        unidad          TEXT,
        precio_total_gs INTEGER,
        fuente_edicion  TEXT,
        fecha_carga     DATE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tcpo_items (
        id                        INTEGER PRIMARY KEY,
        codigo                    TEXT,
        descripcion_pt            TEXT NOT NULL,
        descripcion_pt_normalizada TEXT,
        descripcion_es            TEXT,
        class                     TEXT,
        unidad                    TEXT,
        coef                      REAL,
        precio_brl                REAL,
        precio_total_brl          REAL,
        capitulo                  TEXT,
        subcapitulo               TEXT,
        fila_original             INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS traducciones_cache (
        hash_original     TEXT PRIMARY KEY,
        texto_original    TEXT NOT NULL,
        texto_traducido   TEXT NOT NULL,
        modelo_usado      TEXT,
        fecha_traduccion  TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS mapeos_tcpo_mandua (
        id              INTEGER PRIMARY KEY,
        tcpo_item_id    INTEGER NOT NULL,
        mandua_tipo     TEXT CHECK(mandua_tipo IN ('material', 'mano_obra')),
        mandua_id       INTEGER NOT NULL,
        confianza       INTEGER CHECK(confianza BETWEEN 0 AND 100),
        metodo          TEXT CHECK(metodo IN ('exacto', 'fuzzy', 'embedding', 'manual')),
        revisado_humano INTEGER DEFAULT 0,
        notas           TEXT,
        fecha_mapeo     TIMESTAMP,
        FOREIGN KEY(tcpo_item_id) REFERENCES tcpo_items(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS glosario_terminos (
        id          INTEGER PRIMARY KEY,
        termino_pt  TEXT UNIQUE NOT NULL,
        termino_es  TEXT NOT NULL,
        categoria   TEXT,
        notas       TEXT
    )
    """,
]

INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_tcpo_desc_norm  ON tcpo_items(descripcion_pt_normalizada)",
    "CREATE INDEX IF NOT EXISTS idx_tcpo_capitulo   ON tcpo_items(capitulo)",
    "CREATE INDEX IF NOT EXISTS idx_mat_desc_norm   ON mandua_materiales(descripcion_normalizada)",
    "CREATE INDEX IF NOT EXISTS idx_mo_desc_norm    ON mandua_mano_obra(descripcion_normalizada)",
    "CREATE INDEX IF NOT EXISTS idx_mapeos_tcpo_id  ON mapeos_tcpo_mandua(tcpo_item_id)",
]

TABLES = [
    "mandua_materiales",
    "mandua_mano_obra",
    "mandua_costeo",
    "tcpo_items",
    "traducciones_cache",
    "mapeos_tcpo_mandua",
    "glosario_terminos",
]


def main():
    conn = get_connection()
    with conn:
        for stmt in DDL:
            conn.execute(stmt)
        for stmt in INDICES:
            conn.execute(stmt)

    print(f"{'Tabla':<25} {'Filas':>6}")
    print("-" * 33)
    for table in TABLES:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"{table:<25} {count:>6}")

    conn.close()
    print(f"\nOK: {len(TABLES)} tablas creadas")


if __name__ == "__main__":
    main()
