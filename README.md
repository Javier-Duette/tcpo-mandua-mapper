# TCPO Explorer PY

Aplicación Streamlit local para navegar el catálogo TCPO v15 (Brasil) adaptado para
presupuestos de obra en **Paraguay**, con precios de referencia Mandu'a (edición marzo 2026).

---

## Funcionalidades

| Página | Descripción |
|--------|-------------|
| 🏗️ Dashboard | Métricas de traducción, distribución por relevancia, proyectos activos |
| 🔍 Explorador | Búsqueda y filtrado por capítulo, subcapítulo y relevancia PY; panel de detalle con insumos |
| 📋 Proyectos | Crear proyectos, agregar partidas favoritas, asignar precios Mandu'a, editar cantidades |
| 📤 Exportar | Descargar presupuesto en Excel completo, Excel Dynamo-friendly o CSV |
| ⚙️ Configuración | Lanzar traducción adicional, gestionar glosario PT→ES, estado del sistema |

---

## Requisitos

- Python 3.11+
- Variable de entorno `GEMINI_API_KEY` (solo para el script de traducción A2)

---

## Instalación

```bash
git clone https://github.com/Javier-Duette/tcpo-mandua-mapper.git
cd tcpo-mandua-mapper

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux / macOS

pip install -r requirements.txt
```

---

## Preparar la base de datos

Ejecutar los scripts de carga en orden (solo la primera vez):

```bash
# 1. Cargar TCPO y Mandu'a a SQLite
python scripts/01_cargar_tcpo.py
python scripts/02_cargar_mandua.py

# 2. Extender el schema (proyectos, favoritos, relevancia)
python scripts/A1_extender_schema.py

# 3. Traducir y clasificar capítulos alta prioridad (requiere GEMINI_API_KEY)
echo y | python scripts/A2_traducir_y_clasificar.py --prioridad alta
```

La base de datos resultante (`data/precios.db`) incluye:
- ~40 000 partidas TCPO con traducciones PT→ES
- ~25 000 ítems Mandu'a (materiales + mano de obra)
- Clasificación de relevancia para Paraguay (alta / media / baja / no_aplica)

---

## Correr la aplicación

```bash
streamlit run app/main.py
```

La app queda disponible en `http://localhost:8501`.

---

## Estructura del proyecto

```
tcpo-mandua-mapper/
├── app/
│   ├── main.py                     # Dashboard + configuración de página
│   ├── pages/
│   │   ├── 1_explorador.py         # Navegador de partidas
│   │   ├── 2_proyectos.py          # Gestión de proyectos y favoritos
│   │   ├── 3_exportar.py           # Exportación Excel / CSV
│   │   └── 4_configuracion.py      # Traducción adicional y glosario
│   ├── components/
│   │   ├── filtros.py              # Panel de filtros reutilizable
│   │   ├── tabla_partidas.py       # Tabla paginada interactiva
│   │   ├── detalle_partida.py      # Panel de detalle de una partida
│   │   └── selector_mandua.py      # Modal para asignar precio Mandu'a
│   └── utils/
│       ├── queries.py              # Capa de acceso a datos (SQLite + WAL)
│       ├── formatters.py           # fmt_gs, fmt_brl, relevancia_badge
│       └── export.py               # Generadores de Excel y CSV (openpyxl)
├── scripts/
│   ├── A1_extender_schema.py       # Migración del schema a v2
│   ├── A2_traducir_y_clasificar.py # Pipeline Gemini: traducción + relevancia
│   └── ...                         # Scripts de carga iniciales
├── src/
│   ├── db.py                       # Conexión SQLite
│   ├── gemini_client.py            # Cliente Google Gemini 2.5 Flash
│   └── config.py                   # Rutas y configuración global
├── data/
│   ├── precios.db                  # Base de datos principal (no en repo)
│   └── capitulos_relevantes_py.json
└── requirements.txt
```

---

## Cobertura de datos (abril 2026)

| Métrica | Valor |
|---------|-------|
| Partidas totales TCPO | ~40 000 |
| Traducidas PT→ES | ~29 500 (73 %) |
| Relevancia alta PY | ~19 800 |
| Relevancia media PY | ~5 300 |
| Ítems Mandu'a materiales | ~14 000 |
| Ítems Mandu'a mano de obra | ~11 000 |

---

## Decisiones de arquitectura

| ID | Decisión |
|----|----------|
| D-005 | Streamlit local — sin servidor externo, cero latencia |
| D-006 | Traducción por capítulos bajo demanda (caché por MD5 de descripcion_pt) |
| D-007 | Clasificación de relevancia PY embebida en el mismo llamado Gemini de traducción |
| D-008 | Deduplicación: una traducción por descripcion_pt única, propagada a todos los ítems |

---

## Créditos

- Catálogo TCPO v15 — VOLARE-15_NOV2018 (Editora PINI, Brasil)
- Precios de referencia — Mandu'a edición marzo 2026 (Paraguay)
- Traducción y clasificación — Google Gemini 2.5 Flash
