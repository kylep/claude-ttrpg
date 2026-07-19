# Print-book PDF export — design

**Date:** 2026-07-19
**Status:** Approved, ready for implementation plan

## Problem

The existing export path renders nice print-styled HTML, then round-trips it
through Google Docs' HTML importer (`gws ... application/vnd.google-apps.document`).
That importer is lossy — it discards most CSS, flattens the card layouts, and
mangles tables — so the shared documents look bad. We want genuine, designed
**print books**, not a lossy converter.

## Goal

Produce four standalone booklet **PDFs**, each laid out like a real print book,
rendered deterministically from committed content + committed cover art. Google
Docs export is removed.

## Deliverables

Four self-contained "section" booklets. Each is its own PDF now; each is a
composable module so a future "one big book" is just concatenation + a master
cover.

| PDF | Cover page | Content |
|-----|-----------|---------|
| **The World** | flux banner + title | SVG world map (smaller, top) beside world lore → full-page painted map (`content/maps/WorldMapPainted.png`). Non-spoiler; grows over time. |
| **Classes** | flux banner + title | Text overview per class. No per-class art yet. |
| **Races** | flux banner + title | Per-race card: portrait (`content/art/races/<race>.png`) + description. |
| **Bestiary** | flux banner + title | Per-creature card: portrait (`content/art/bestiary/<mon>.png`) + stats/description. |

Each booklet: **one cover page, then content. No index / TOC.**
Cover = bold fantasy display title + an evocative flux image whose prompt is
derived from real in-game content (e.g. Bestiary cover = actual game creatures
mid-brawl).

## Architecture — two stages

### Stage A · Asset generation (one-time, only spend, committed)

- Generate **4 cover banners** via the image-gen / artist loop (`tools/imagegen.py`,
  flux model). Prompts built from real in-game content.
- Commit to `games/familyrpg/content/art/covers/{world,classes,races,bestiary}.png`.
- Shared location under the content tree so the planned web UI reads the same
  files. This is the only BFL spend; a deliberate, tiny exception to the
  standing "procedural-SVG / no image spend" direction.

### Stage B · Book build (deterministic, free, repeatable)

- No API calls. Re-runnable anytime content changes.
- Reuse the existing `export.py` content loaders (`_race_html`, `_monster_html`,
  `_class_html`, world/lore readers) where practical; add print-book templates.
- Render via **WeasyPrint** → `exports/<section>.pdf`.
- Layout micro-decisions may be made by Claude; content stays data-driven so it
  survives content churn.

## Engine — WeasyPrint

Pure-Python, `pip install weasyprint`. Real CSS Paged Media: full-bleed cover
pages, deterministic page breaks, margin page numbers, running section header.
Native dependency: `pango` (+ cairo/harfbuzz/fontconfig) via `brew install pango`
— verified as the first implementation step. A bundled open fantasy display font
(e.g. Cinzel, OFL) ships in-repo so builds are reproducible across machines.

## Layout language

Shared print stylesheet evolving today's `_STYLE`:

- Serif body; bundled fantasy display face for titles.
- Full-bleed cover pages (image + overlaid title).
- Drop-cap section openers.
- Framed art; repeating art+text **cards** for roster sections (races, bestiary).
- Margin page numbers + running section header.
- Per-section templates: `cover`, `world` (map + lore), `roster` (races /
  bestiary), `text-overview` (classes).

## CLI

Extend the existing `export` Typer app:

```
engine export book world     [--game games/familyrpg] [--out exports]
engine export book classes
engine export book races
engine export book bestiary
engine export book all        # renders all four
```

Each prints `{"file": "<path.pdf>"}`. Reuses `resolve_source()` for content/ruleset
resolution (works both inside a world via canon/ and repo-side via `--game`).

## Cleanup

- Remove the Google Docs / `gws` upload path entirely.
- Replace the `export-docs` skill with a new `export-pdf` skill describing the
  two-stage flow (generate covers once → build PDFs).
- Keep or retire the legacy HTML `render_game/world/campaign`? Decision: keep the
  HTML renderers (still used by anything reading raw HTML) but the *shared/
  printable* deliverable is now the book PDFs. Revisit if HTML has no consumer.

## Layout / module boundaries

- **New module** `engine/src/ttrpg_engine/bookexport.py`: section templates +
  WeasyPrint render. One clear job: content dict → styled PDF bytes. Depends on
  `export.py` loaders and the print stylesheet; no state mutation.
- **Print stylesheet**: a `_BOOK_STYLE` string (or `.css` asset) separate from the
  screen `_STYLE`.
- **Cover assets**: read from the content tree, resolved fail-open (missing cover
  → title-only cover page, never a hard failure — mirrors existing fail-open
  image resolution).
- **Font asset**: bundled under the engine package so WeasyPrint finds it.

## Testing

- `bookexport` renders a valid non-empty PDF for each section from
  `games/familyrpg` (assert file exists, `%PDF` header, >1 page).
- Fail-open: missing cover image / missing portrait still renders a PDF.
- Content-driven: adding a creature to content shows up without code change.

## Success criteria

- `engine export book all --game games/familyrpg` produces four PDFs that look
  like designed booklets (cover + laid-out content), no Google Docs step.
- Rebuild is deterministic and offline given committed covers.
- Covers live in the shared content art tree for web-UI reuse.
