---
name: export-pdf
description: Use when the operator wants printable/shareable PDF booklets of the game — World, Classes, Races, and Bestiary — as designed print books.
---

# Export print-book PDFs

Renders four designed booklet PDFs from committed content and committed cover
art. Deterministic and offline: no API calls at build time.

## Prerequisite (one-time)

WeasyPrint needs Pango. On macOS: `brew install pango`. If a render dies with
`cannot load library 'libpango'`, that's the missing dep.

## 1. Build the PDFs

Inside a world (uses `canon/` + the world's pinned game):

    engine export book all

Repo-side (uses a game's own `content/` + ruleset):

    engine export book all --game games/familyrpg

Or one at a time: `engine export book bestiary --game games/familyrpg`.
Default output dir is `./exports/`; pass `--out DIR` to change it. Each file
emits `{"file": "<path>.pdf"}`.

## 2. Cover art (optional, one-time, costs BFL spend)

Each booklet shows a full-page cover banner from
`content/art/covers/{world,classes,races,bestiary}.png`. If a cover is
missing the build still succeeds with a text-only cover page. To generate the
banners, use the **image-gen** skill with prompts drawn from real in-game
content (e.g. the Bestiary cover = actual game creatures in a clash), write
them to `games/<game>/content/art/covers/`, and commit. These assets are
shared with the web UI.

## 3. Report

Report the four local PDF paths from step 1. There is no upload step — the PDF
is the deliverable.
