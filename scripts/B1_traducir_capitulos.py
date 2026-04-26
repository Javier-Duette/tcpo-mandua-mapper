"""B1_traducir_capitulos.py — Traduce los capítulos de PT a ES.

Reemplaza los nombres de capítulos en `tcpo_items.capitulo` (manteniendo
el prefijo numérico para no romper ordenamiento ni búsquedas).
"""
import sqlite3
from pathlib import Path

ROOT    = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "precios.db"

# Mapeo manual PT → ES (adaptado al contexto paraguayo)
CAPITULOS = {
    "02. Serviços Iniciais":                                "02. Servicios iniciales",
    "04. Infraestrutura":                                   "04. Infraestructura",
    "05. Superestrutura":                                   "05. Superestructura",
    "06. Alvenarias, fechamentos e divisórias":             "06. Mampostería, cerramientos y tabiquería",
    "09. Coberturas":                                       "09. Cubiertas",
    "10. Impermeabilização":                                "10. Impermeabilización",
    "11. Isolamento térmico e acústico":                    "11. Aislamiento térmico y acústico",
    "12. Esquadrias":                                       "12. Aberturas (puertas y ventanas)",
    "13. Sistemas hidráulicos":                             "13. Sistemas hidráulicos y sanitarios",
    "15. Sistemas de prevenção e combate a incêndio":       "15. Sistemas de prevención y combate de incendios",
    "16. Sistemas elétricos":                               "16. Sistemas eléctricos",
    "17. Automação, sistemas de telecomunicação e segurança": "17. Automatización, telecomunicaciones y seguridad",
    "18. Sistemas de proteção contra descargas atmosféricas": "18. Pararrayos y protección contra descargas atmosféricas",
    "19. Ar condicionado, ventilação e exaustão":           "19. Aire acondicionado, ventilación y extracción",
    "20. Revestimentos de superfícies":                     "20. Revestimientos de superficies",
    "21. Forros":                                           "21. Cielorrasos",
    "22. Pisos":                                            "22. Pisos",
    "23. Revestimentos de paredes":                         "23. Revestimientos de paredes",
    "24. Pinturas":                                         "24. Pinturas",
    "26. Louças, metais e acessórios sanitários":           "26. Sanitarios, grifería y accesorios",
    "27. Vidros":                                           "27. Vidrios",
    "30. Urbanização e serviços externos":                  "30. Urbanización y servicios externos",
    "31. Transporte":                                       "31. Transporte",
    "32. Serviços complementares e apoio":                  "32. Servicios complementarios y de apoyo",
    "36. Equipamentos":                                     "36. Equipos",
}


def main() -> None:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON")

    print(f"Traduciendo {len(CAPITULOS)} capítulos…")

    actualizados = 0
    no_encontrados = []
    for pt, es in CAPITULOS.items():
        cur = conn.execute(
            "UPDATE tcpo_items SET capitulo = ? WHERE capitulo = ?",
            (es, pt),
        )
        if cur.rowcount > 0:
            print(f"  [OK] {pt!r:55s} -> {es!r}  ({cur.rowcount} filas)")
            actualizados += cur.rowcount
        else:
            no_encontrados.append(pt)

    conn.commit()
    conn.close()

    print()
    print(f"Total filas actualizadas: {actualizados}")
    if no_encontrados:
        print(f"\nNo encontrados en DB ({len(no_encontrados)}):")
        for c in no_encontrados:
            print(f"  - {c!r}")


if __name__ == "__main__":
    main()
