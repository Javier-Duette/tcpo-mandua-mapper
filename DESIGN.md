---
meta:
  product: TCPO Explorer PY
  tagline: Catálogo TCPO v15 adaptado para presupuestos de obra en Paraguay
  domain: Construction cost estimation / quantity surveying
  audience: Civil engineers, quantity surveyors, students adapting Brazilian TCPO data to the Paraguayan market
  language: Spanish (Paraguayan register, with bilingual PT/ES data)
  platform: Streamlit web app (multi-page, dark-mode-first)
  tone: Pragmatic, instrumental, slightly informal — a working tool, not a polished consumer product

color:
  scheme: dark-first
  base:
    background: "#0E1117"          # canvas — Streamlit dark default
    surface: "#262730"             # raised surfaces (cards, sidebar, expanders)
    surface-elevated: "#1E2530"    # selected rows, focused panels
    overlay-tint: "rgba(0, 0, 0, 0.04)"  # subtle wash on header cards
    text-primary: "#FAFAFA"
    text-secondary: "#A6A8AB"
    text-muted: "#8B8E94"
    divider: "rgba(250, 250, 250, 0.12)"

  semantic:
    relevance:
      high: "#28a745"              # 🟢 green — priority for local market
      medium: "#ffc107"            # 🟡 amber
      low: "#fd7e14"               # 🟠 orange
      not-applicable: "#dc3545"    # 🔴 red — out of scope for Paraguay
      unclassified: "#adb5bd"      # ⚪ neutral gray — pending review
    review-flag: "#f0a500"         # 🔬 amber-orange — items in quarantine
    chart-default: "#1f77b4"       # blue — bar charts, primary data viz

  selection:
    background: "#1e2a3a"          # dark blue-gray panel
    border-accent: "#4a9eff"       # 3-4px left border on selected/highlighted
    text: "#cdd9e5"                # light gray for body text inside selection
    code-emphasis: "#7ab3ff"       # lighter blue for monospace item codes

  status:
    success: "#28a745"
    error: "#dc3545"
    warning: "#ffc107"
    info: "#1f77b4"

  custom-namespace:
    py-prefix-tint: inherit        # custom items use the same palette;
                                   # the "PY." code prefix alone signals authorship

typography:
  family:
    base: "Source Sans 3, ui-sans-serif, system-ui, sans-serif"
    mono: "Source Code Pro, ui-monospace, SFMono-Regular, monospace"
  scale:
    metric-value: "2.25rem"        # st.metric headline numbers
    h1: "2rem"                     # page titles (e.g. "🏗️ TCPO Explorer PY")
    h2: "1.5rem"                   # section titles inside tabs
    h3: "1.25rem"                  # subsection
    body: "1rem"
    caption: "0.875rem"            # st.caption — secondary info, hints
    selection-bar: "0.85em"        # condensed inline metadata
  weight:
    regular: 400
    bold: 700
  treatments:
    item-code: bold                # always bold codes like "22.109.000060.SER"
    description-truncation: "ellipsis '…' at 60–80 chars in lists; full in detail"
    bilingual-fallback: "show ES; fallback to PT in italic muted gray when missing"

spacing:
  scale:
    none: "0"
    xs: "4px"
    sm: "6px"
    md: "8px"
    lg: "10px"
    xl: "12px"
    2xl: "16px"
    3xl: "24px"
  card-padding: "6px 10px"
  selection-bar-padding: "6px 12px"
  table-cell-padding: "8px 12px"
  form-row-gap: "12px"

radius:
  card: "4px"
  pill: "6px"
  button: "4px"
  input: "4px"
  badge: "4px"

border:
  hairline: "1px"
  card: "1px solid rgba(255, 255, 255, 0.10)"
  accent-thin: "3px"               # selection bar
  accent: "4px"                    # detail-panel header (uses relevance color)

elevation:
  # The product is intentionally flat. Depth is conveyed by background tint
  # and accent borders, not drop shadows.
  flat: "none"
  card: "0 0 0 1px rgba(255, 255, 255, 0.06)"
  sticky-bar: "0 2px 8px rgba(0, 0, 0, 0.25)"  # rare — only for floating toasts

motion:
  page-rerun: "instant — Streamlit rerun on every widget interaction"
  toast: "4s auto-dismiss, slide from top-right"
  hover: "~150ms ease-out (Streamlit default)"
  celebration: "balloons burst (st.balloons) for entity-creation moments"
  no-skeletons: "use spinners only for blocking operations >300ms"

iconography:
  system: emoji-only
  rationale: |
    All icons are Unicode emoji. No SVG sprites, no icon fonts. This makes the
    visuals dependency-free, renders consistently across OSes, and reinforces
    the friendly, informal Spanish-language voice. Emojis function as both
    icons and small mood-setters.
  navigation:
    home: "🏗️"
    explorer: "🔍"
    projects: "📋"
    export: "📊"
    config: "⚙️"
    custom-items: "🏗️"
  taxonomy:
    service: "🔧"
    leaf-item: "📦"
    folder-chapter: "📂"
    folder-subchapter: "📁"
    glossary: "📖"
    money: "💰"
    translate: "🌐"
  actions:
    edit: "✏️"
    save: "💾"
    delete: "🗑️"
    add: "➕"
    cancel: "✕"
    confirm: "⚠️"
    reload: "🔄"
    search: "🔍"
    nav-prev: "◀"
    nav-next: "▶"
    expand-toggle: "▶ / ▼"
  state:
    favorite: "⭐"
    review-flag: "🔬"
    success: "✅"
    warning: "⚠️"
    info: "💡"
    relevance-high: "🟢"
    relevance-medium: "🟡"
    relevance-low: "🟠"
    relevance-na: "🔴"
    relevance-unclassified: "⚪"

layout:
  page-width: wide                 # Streamlit layout="wide" universally
  sidebar:
    state-default: expanded
    state-pages: collapsed         # detail pages prefer full canvas
    contents:
      - "🏗️ Brand header (sidebar title)"
      - "Active project selector (selectbox)"
      - "Version footer caption"
  patterns:
    explorer-three-column: "ratios [2.5, 5, 2.5] — filters | table | detail"
    form-two-column: "ratios [1, 1] — inputs left | inputs right"
    dashboard-metrics: "five-column row of st.metric"
    tabs-per-page: "2 to 5 tabs"
    expander-density: "one expander per item in long lists; nested for sub-services"
  density:
    table-row-height: "54px"
    line-height: 1.35
    description-cell: "wrap to ~2 lines, no truncation; full text via tooltip + selection bar"
    metric-tile-density: "5 across at desktop, no caps in metric numbers"

currency:
  primary:
    name: Guaraní paraguayo
    code: PYG
    symbol: "Gs."
    format: "Gs. 1.234.567"
    thousands-separator: "."
    decimal-separator: none        # integer Guaraníes only
  reference:
    name: Real brasileño
    code: BRL
    symbol: "R$"
    format: "R$ 1.234,56"
    thousands-separator: "."
    decimal-separator: ","
    presentation: shown muted as "Ref. BRL" beside primary
  empty-value: "—"                 # em-dash when null / missing
  coefficient-format: "0.0001"     # up to 4 decimals, trailing zeros trimmed

interaction:
  selection:
    mode: single-row
    indicator: native checkbox column on the left of tables
    feedback: |
      Selected row is echoed in a slim "selection bar" above the table —
      bg #1e2a3a, 3px left border #4a9eff, code in mono #7ab3ff —
      so the full description stays readable while wrapped table cells
      remain compact.
  inline-edit:
    pattern: "click ✏️ → text input + [💾 Guardar] [✕ Cancelar]"
    scope: "applies to descripción, precio, fuente, unidad on owned items"
    persistence: "save propagates to all rows sharing the same código + cascades prices"
  destructive:
    pattern: two-step-confirm
    states: "[🗑️ Eliminar] → warning panel → [⚠️ Confirmar] [✕ Cancelar]"
    scope: "all delete actions (favorito, item custom, proyecto)"
  feedback:
    transient: "st.toast — 4s, top-right"
    persistent-block: "st.success / st.error / st.warning / st.info"
    celebration: "st.balloons on first-time creation events"
  search:
    debounce: "minimum 2 characters before issuing query"
    placement: "inline at top of relevant column or panel"
    modes: "Descripción / Código / Ambos (radio toggle)"
  filter-counter:
    pattern: "🔵 N filtro(s) activo(s) — followed by [🗑 Limpiar] button"
    behavior: "clear button is disabled when count is 0"

components:
  header-card:
    structure: "left border (4px solid relevance color) + bold código + relevance badge + class label"
    background: "rgba(0, 0, 0, 0.04)"
    radius: "4px"
    padding: "6px 10px"
    margin-bottom: "8px"
  selection-bar:
    structure: "código in mono blue + full description in light gray"
    background: "#1e2a3a"
    border-left: "3px solid #4a9eff"
    radius: "6px"
    padding: "6px 12px"
    font-size: "0.85em"
  metric-tile: "Streamlit st.metric — value, label, optional delta"
  data-editor:
    use-when: "editing tabular data (project lines, glossary terms, price overrides, custom service composition)"
    column-flags: "disabled columns rendered muted; editable columns get hover affordance"
    save-pattern: "explicit [💾 Guardar cambios] button — never auto-save"
  expander:
    use-when: "long lists with per-item details (mis ítems, glosario matches, sub-services)"
    title-format: "{icon} **{código}** · {clase} · {descripción[:60]} — Gs. {precio}"
  tabs:
    use-when: "page-level navigation between related but distinct workflows"
    icon-prefix: "always emoji-prefixed (e.g. ➕ Nuevo ítem)"

content-voice:
  language: Spanish (Paraguayan register)
  formality: informal-professional ("vos" forms, contractions ok, no slang)
  microcopy-examples:
    success: "✅ Ítem creado: PY.22.000005.MAT"
    empty-state: "Todavía no creaste ningún ítem propio."
    cta: "Buscalos en el Explorador y agregalos con ⭐"
    confirmation: "¿Confirmar eliminación de «{nombre}»?"
    blocking: "❌ El código PY.22.000005.MAT ya existe."
  bilingual-data:
    rule: "Catalog data has PT (original) + ES (Paraguayan). UI is monolingual ES."
    fallback: "When ES translation is missing, render PT in italic muted gray."

namespace:
  user-content-prefix:
    pattern: "PY.{cap}.{NNNNNN}.{suf}"
    example: "PY.22.000005.MAT"
    rationale: |
      User-authored items are namespaced with the literal "PY." prefix to
      visually separate them from TCPO originals (which begin with chapter
      digits like "22.109..."). The prefix is functional but also a brand
      signal — owners see their items at a glance.
---

# TCPO Explorer PY — Visual Identity

## Personality

The product is a **working tool**, not a showpiece. It belongs in the same family as a spreadsheet, an ERP module, or a cost-estimation desktop application — visually dense, information-rich, oriented toward the engineer who has fifty things to look up and three estimates due Friday. The visual restraint is deliberate: nothing should distract from the catalog.

Three strands give the product its character:

1. **Bilingual construction data**, presented Spanish-first with Portuguese fallbacks. The user is translating and adapting Brazilian TCPO entries to the Paraguayan market, so the UI keeps both languages available without privileging one cosmetically.

2. **A dark, near-flat aesthetic** inherited from Streamlit and consciously left alone. There are no gradients, no skeuomorphism, no decorative shadows. Depth is conveyed by **subtle background tint changes** and **accent left-borders** in semantic colors — never by elevation in the Material sense.

3. **Emoji-as-icon throughout.** Every action, every state, every taxonomy node carries an emoji. This is the single most defining choice of the system. It keeps the codebase free of icon dependencies, lets the UI render identically across OSes, and lends the whole tool a slightly informal, conversational quality that fits the Spanish microcopy.

## Color story

The palette is **monochrome dark + a five-step semantic accent ramp**:

- **Canvas, surface, elevated** are flat grays in the `#0E…#26…#1E` range. They convey hierarchy through brightness alone.
- **Relevance** is the load-bearing color system: a five-step scale (green → amber → orange → red → gray) that classifies how applicable a Brazilian catalog item is to Paraguay. This scale appears as colored emoji dots in tables, as colored left-borders on detail-panel headers, and as colored badge text. It is the primary way the user navigates the catalog cognitively.
- **Selection blue** (`#4a9eff` border, `#1e2a3a` panel, `#7ab3ff` code mono) is the only chromatic interaction accent. It indicates the currently-selected row, the active project, and primary CTAs. There is no secondary accent.
- **Review amber** (`#f0a500`) is the single quarantine signal — items the user has flagged 🔬 for later research. It deliberately echoes the medium-relevance amber but is brighter and warmer.

Status colors (success, error, warning, info) follow Streamlit defaults. They are loud on purpose: this is a tool that touches financial data, so confirmation messages and errors should be unmissable.

## Typography & rhythm

Type is **Streamlit defaults, undecorated**. Source Sans 3 for everything but item codes, which always render in mono and bold (e.g. `22.109.000060.SER`). The codebase resists the temptation to introduce a display font or display weight — page titles are simply the body family at H1 scale with an emoji prefix.

Tables are dense by design: `54px` row height with `1.35` line height, descriptions wrap to two lines with no truncation. The selection bar at the top of the table is the safety valve — it shows the full description of whatever row is highlighted, in a smaller font (`0.85em`) and the muted-blue palette, so the table itself can stay compact.

## Spacing & layout

The layout grammar is **Streamlit's column system applied with restraint**:

- **Three-column** for the main exploration view: filters left, table center, detail right (`[2.5, 5, 2.5]`). This is the canonical screen.
- **Two-column** for forms and editors. Always balanced.
- **Five-column** for the dashboard metrics row.
- **Tabs** for grouping related workflows on the same page (configuración, ítems custom).

The sidebar is the global anchor: brand name, active-project selector, version. It is expanded on the home page and collapsed on detail pages so the canvas can breathe.

## Interaction patterns

A small set of patterns is reused everywhere, which is what gives the product its consistency:

- **Click-to-select** in tables — single row at a time, with a checkbox-style affordance in the leftmost column. Selection echoes into a "selection bar" above the table showing the full description.
- **Inline edit with the ✏️ pencil** — values are read-only by default; clicking ✏️ swaps the value for an input plus `💾 Guardar` / `✕ Cancelar` buttons. This pattern is used for descriptions, prices, sources, and units. It avoids modal dialogs.
- **Two-step confirm for any destructive action** — clicking 🗑️ never deletes immediately; it reveals a warning panel with explicit `⚠️ Confirmar` and `✕ Cancelar`. Permanent operations always require deliberate intent.
- **Toast for ephemera, persistent banners for blocking.** A successful save toasts; an error stays on screen until acknowledged.
- **Balloons on creation** — when the user creates their first custom item, a brief Streamlit balloons burst marks the moment. This is the only piece of pure delight in an otherwise utilitarian interface, and it is reserved for entity-creation moments.

## Owned-content namespace

User-authored items are visually namespaced by prefixing their codes with the literal string `PY.` (e.g. `PY.22.000005.MAT`). This is functional — it prevents collision with TCPO's chapter-numbered codes — but it is also a quiet branding signal: when scrolling a long table, the user sees their own work at a glance because the code shape is unmistakably different from `22.109.000060.SER`.

## Currency presentation

The product handles two currencies with deliberate asymmetry:

- **Guaraní (`Gs.`)** is primary. Format: `Gs. 1.234.567` — periods as thousands, no decimals (Paraguayan convention; Guaraní rarely shows fractional amounts in construction estimating).
- **Real (`R$`)** is reference, shown as smaller "Ref. BRL" labels beside the primary value. It documents provenance from the original Brazilian catalog without competing for attention.

Missing values render as a single em-dash `—`. Coefficients show up to four decimal places with trailing zeros trimmed (`1.05`, `0.0291`).

## Voice

Microcopy is **informal Spanish-Paraguayan**: `vos` forms, contractions, no jargon-for-jargon's-sake. Errors say what's wrong and how to fix it. Empty states tell the user what to do next. Confirmations name the entity by code. Success messages are direct: `✅ Ítem creado: PY.22.000005.MAT`.

The tone matches the audience — civil engineers and students working on real estimates — and it matches the visual restraint: practical, no-nonsense, but warm enough through the emoji vocabulary to feel like a tool that understands what its user is doing.
