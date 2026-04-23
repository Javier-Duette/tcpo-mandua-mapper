"""A1_extender_schema.py - Extiende data/precios.db para el nuevo rumbo del proyecto.

Agrega tablas: proyectos, favoritos, notas_partida
Extiende: tcpo_items (relevancia_py, ...), traducciones_cache (metadata_json)
Crea indices nuevos.
Idempotente: usa CREATE TABLE IF NOT EXISTS y chequea columnas antes de ALTER.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import get_connection


def _column_exists(conn, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == column for r in rows)


def _index_exists(conn, name: str) -> bool:
    r = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name=?", (name,)
    ).fetchone()
    return r[0] > 0


def main():
    conn = get_connection()
    print("Extendiendo schema de data/precios.db...")
    print()

    # -----------------------------------------------------------------------
    # 1. Tabla proyectos
    # -----------------------------------------------------------------------
    conn.execute("""
        CREATE TABLE IF NOT EXISTS proyectos (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre             TEXT NOT NULL,
            descripcion        TEXT,
            fecha_creacion     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            activo             INTEGER DEFAULT 1
        )
    """)
    print("  [OK] tabla proyectos")

    # -----------------------------------------------------------------------
    # 2. Tabla favoritos
    # -----------------------------------------------------------------------
    conn.execute("""
        CREATE TABLE IF NOT EXISTS favoritos (
            id                        INTEGER PRIMARY KEY AUTOINCREMENT,
            proyecto_id               INTEGER NOT NULL,
            tcpo_item_id              INTEGER NOT NULL,
            cantidad_estimada         REAL,
            notas_propias             TEXT,
            mandua_tipo               TEXT,
            mandua_id                 INTEGER,
            precio_unitario_manual_gs INTEGER,
            orden                     INTEGER,
            fecha_agregado            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(proyecto_id)  REFERENCES proyectos(id) ON DELETE CASCADE,
            FOREIGN KEY(tcpo_item_id) REFERENCES tcpo_items(id),
            UNIQUE(proyecto_id, tcpo_item_id)
        )
    """)
    print("  [OK] tabla favoritos")

    # -----------------------------------------------------------------------
    # 3. Tabla notas_partida
    # -----------------------------------------------------------------------
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notas_partida (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            tcpo_item_id       INTEGER NOT NULL UNIQUE,
            nota               TEXT NOT NULL,
            fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(tcpo_item_id) REFERENCES tcpo_items(id)
        )
    """)
    print("  [OK] tabla notas_partida")
    print()

    # -----------------------------------------------------------------------
    # 4. ALTER TABLE tcpo_items - columnas nuevas
    # -----------------------------------------------------------------------
    alteraciones = [
        (
            "relevancia_py",
            "TEXT CHECK(relevancia_py IN "
            "('alta','media','baja','no_aplica','sin_clasificar')) "
            "DEFAULT 'sin_clasificar'",
        ),
        ("relevancia_justificacion", "TEXT"),
        ("fecha_traduccion",         "TIMESTAMP"),
        ("fecha_clasificacion",      "TIMESTAMP"),
    ]
    for col, typedef in alteraciones:
        if not _column_exists(conn, "tcpo_items", col):
            conn.execute(f"ALTER TABLE tcpo_items ADD COLUMN {col} {typedef}")
            print(f"  [OK] tcpo_items ADD COLUMN {col}")
        else:
            print(f"  [ya existe] tcpo_items.{col}")

    print()

    # -----------------------------------------------------------------------
    # 5. ALTER TABLE traducciones_cache - columna metadata_json
    # -----------------------------------------------------------------------
    if not _column_exists(conn, "traducciones_cache", "metadata_json"):
        conn.execute("ALTER TABLE traducciones_cache ADD COLUMN metadata_json TEXT")
        print("  [OK] traducciones_cache ADD COLUMN metadata_json")
    else:
        print("  [ya existe] traducciones_cache.metadata_json")

    print()

    # -----------------------------------------------------------------------
    # 6. Indices nuevos
    # -----------------------------------------------------------------------
    indices = [
        ("idx_tcpo_relevancia", "tcpo_items(relevancia_py)"),
        ("idx_tcpo_cap_subcap",  "tcpo_items(capitulo, subcapitulo)"),
        ("idx_fav_proyecto",     "favoritos(proyecto_id)"),
        ("idx_fav_tcpo_item",    "favoritos(tcpo_item_id)"),
    ]
    for idx_name, idx_def in indices:
        if not _index_exists(conn, idx_name):
            conn.execute(f"CREATE INDEX {idx_name} ON {idx_def}")
            print(f"  [OK] CREATE INDEX {idx_name}")
        else:
            print(f"  [ya existe] INDEX {idx_name}")

    conn.commit()
    conn.close()

    print()
    print("Schema extendido correctamente.")
    print("  Tablas nuevas    : proyectos, favoritos, notas_partida")
    print("  Cols en tcpo_items: relevancia_py, relevancia_justificacion,")
    print("                      fecha_traduccion, fecha_clasificacion")
    print("  Col en cache     : traducciones_cache.metadata_json")
    print("  Indices nuevos   : idx_tcpo_relevancia, idx_tcpo_cap_subcap,")
    print("                     idx_fav_proyecto, idx_fav_tcpo_item")


if __name__ == "__main__":
    main()
