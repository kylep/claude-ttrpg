# Glossary web view — design

**Date:** 2026-07-19
**Status:** Approved (user: "you decide the rest, work till done"), ready for plan

## Goal

Add a **Glossary** to the live world viewer: a full-screen, in-window web view of
the four booklets (World, Classes, Races, Bestiary) with sidebar nav and
app-native rendering — reusing the content `bookexport` already builds for the
PDFs, respecting the player/GM lens, and exposing a clean API a future per-player
mobile app can reuse.

## Shape

- A **"Glossary" button** in the viewer header opens a **full-screen overlay**
  (`#glossary-overlay`) in the same browser window — no new tab.
- Left **sidebar** lists the four sections (World / Classes / Races / Bestiary).
  Selecting one loads its cover banner + content into the content pane.
- Closes back to the live game (Escape / backdrop / close button — matching the
  existing entity-sheet overlay conventions).

## Content reuse — split content-building from PDF rendering

`bookexport` currently builds each section's HTML *inline inside* `build_races`,
`build_bestiary`, `build_classes` (and `_world_html` for world), then renders to
PDF. Refactor so the **content body** and the **PDF wrapper** are separate, and
both the PDF path and the web path share one content source:

- Extract `_races_body(src) -> str`, `_classes_body(src) -> str`,
  `_bestiary_body(src, lens="gm") -> str`, `_world_body(src) -> str` — each
  returns the inner content HTML (the cards / roster / world content), no page
  shell.
- `build_races(src)` = `render_pdf(_document("Races", subtitle, cover, _races_body(src)), content_dir)`;
  same shape for the others. `build_bestiary` calls `_bestiary_body(src, "gm")`
  (the PDF is the full reference book). Behaviour of the existing CLI/PDF path is
  unchanged.
- Add web API helpers:
  - `glossary_manifest(src) -> list[{"id","title","cover"}]` — the four sections,
    `cover` = fail-open resolved `art/covers/<id>.png` (or `None`).
  - `glossary_section(src, name, lens) -> {"id","title","cover","body_html"}` —
    raises on unknown `name` (caller maps to 404).
  - `GLOSSARY_TITLES = {"world":"The World","classes":"Classes","races":"Races","bestiary":"Bestiary"}`.

## Lens (respect it)

Only the **Bestiary** is lens-sensitive:

- **GM lens (`/gm`, `lens=gm`):** full stat blocks — AC, HP, Speed, XP,
  difficulty, attacks, notes (identical to the PDF).
- **Player lens (`/`, `lens=player`):** each creature shows **name + art +
  description only**; the GM-only fields (AC, HP, XP, difficulty, attacks, notes)
  are omitted. All creatures still appear (per decision — the bestiary is a
  browsable menagerie; only the numbers are secret). Speed is treated as a
  stat and hidden with the rest.
- **Classes, Races** (player-facing rules) and **World** (non-spoiler text)
  render fully in both lenses.

The PDF export path always uses `lens="gm"` (unchanged full book).

## Backend routes (`serve.py`)

Two GET routes on the existing per-world server; lens derived from `?lens=` as the
other routes do (`gm` → "gm", else "player"):

- `/api/glossary` → `glossary_manifest(src)` (JSON list).
- `/api/glossary/<section>` → `glossary_section(src, section, lens)` (JSON obj);
  unknown section → `{"error":"not found"}`, 404.

`src` is resolved with `export_mod.resolve_source(self.root, None)` (world canon +
pinned game — same content the world viewer already shows). New imports in
`serve.py`: `from ttrpg_engine import bookexport, export as export_mod`.

## Images — no rewriting

Section `body_html` references art by content-relative path (e.g.
`<img src="art/bestiary/orc.png">`, `<img class="banner">` covers via the
manifest `cover` field). Served pages live at `/` and `/gm`, so a relative
`art/...` URL resolves in the browser to `/art/...`, which the existing
`_content_art_file` route serves. The manifest `cover` (e.g. `art/covers/world.png`)
is prefixed with `/art/`-relative resolution the same way. No path rewriting, no
new static route.

## Frontend (`viewer.html`)

- Header **Glossary button**; `#glossary-overlay` (fixed, full-screen, hidden).
- JS: `openGlossary()` fetches the manifest, builds the sidebar, loads the first
  section. `loadGlossarySection(id)` fetches `/api/glossary/<id>?lens=<LENS>` and
  fills the content pane: cover banner `<img>`, `<h1>` title, then `body_html` via
  `innerHTML`. Close via Escape / backdrop / button (reuse existing conventions;
  `LENS` const already exists).
- **Rendering:** style the content with the viewer's own theme (its CSS vars,
  fonts, dark palette), scoped under `.glossary` so bookexport's `.card`/`.tag`/
  `.roster` class names (which also exist on the print side and on the viewer's
  aside panels) don't collide. Responsive: sidebar collapses above the content on
  narrow screens (forward-looking for the eventual mobile app). `.glossary .fullbleed img`
  becomes a normal responsive image (the print page-break is irrelevant on screen).

## Security / trust

`body_html` is server-rendered: all author text is escaped via `esc`, world lore
via `render_markdown`+`sanitize_html`; the world-map SVG is inlined raw as a
first-party trusted asset (same trust model as the PDF exporter). Inserting it via
`innerHTML` is acceptable under that model — the content carries no script. This
is a documented decision, consistent with the existing exporter.

## Files

- **Modify** `engine/src/ttrpg_engine/bookexport.py` — split body builders, lens,
  glossary helpers.
- **Modify** `engine/src/ttrpg_engine/serve.py` — two routes + imports.
- **Modify** `engine/src/ttrpg_engine/viewer.html` — button, overlay, nav, fetch,
  screen CSS.
- **Modify** `engine/tests/test_bookexport.py` — lens + glossary helper tests.
- Add a serve route test if the repo has an http test pattern; else a focused
  glossary-helper test suffices and the route is verified live by the controller.

## Testing / verification

- Unit: `_bestiary_body(src,"player")` omits AC/HP/XP/attacks; `"gm"` includes
  them. `glossary_manifest` returns 4 sections with titles. `glossary_section`
  returns `body_html` and raises on unknown. `build_*` still emit valid PDFs
  (regression).
- Controller live-verify: `engine serve`, curl `/api/glossary`,
  `/api/glossary/bestiary?lens=player` vs `?lens=gm` (assert stats differ), and
  screenshot the overlay if a headless browser is available.

## Success criteria

- Glossary button opens an in-window overlay; the four sections render with cover
  banners and app-native styling and readable nav.
- Player lens hides bestiary numbers; GM lens shows them; classes/races/world full
  in both.
- PDF export unchanged. API is clean JSON reusable by a future mobile client.
