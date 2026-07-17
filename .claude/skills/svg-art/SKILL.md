---
name: svg-art
description: Use when creating or updating SVG art for claude-ttrpg (node vignettes, map assets, card art) - runs the artist/reviewer adversarial loop in the house style.
---

# SVG art — the adversarial loop

Every piece of authored art goes through an artist and a hostile reviewer so
the operator never has to be the one squinting at jank.

## House style (binds every piece)

- **Palette** — parchment `#e8dcc0` ground, aged blotch `#d8c9a6`, ink
  `#4a3527`, faded ink `#8a7a5f`, pale plaster `#efe6d2`, moss `#6f7f52` /
  `#7d8a63`, roof-clay `#a3543c`, water `#4a6a7a`, ember accent `#a33d2f`
  (sparingly — it means "the party / attention"), stone `#c9bda3` /
  `#b3a68a`, deep shadow `#241c14`. Stay inside it; tints of these are fine.
- **Line language** — visible ink outlines, two weights: structural
  ~1.6–2.4, fine detail ~0.8–1.2. Flat fills, no gradients, no filters.
  Slight hand-wobble is welcome; mechanical perfection is not.
- **Composition** — one focal subject; foreground / midground / background;
  generous negative space; strong silhouettes that survive being a
  thumbnail. Frame vignettes with soft vignette edges or a simple border,
  not hard crops through subjects.
- **Format** — pure static SVG, `viewBox` set (node vignettes: `0 0 420
  280`), no width/height on the root. Banned: `<script>`, event attributes,
  `<foreignObject>`, external hrefs, raster `<image>`, animation.

## Where art lives

- Game-owned art ships in `games/<game>/content/art/<id>.svg` — world init
  copies content into `canon/`, so every new world inherits it.
- World-local art goes straight into the world's `canon/art/<id>.svg`.
- A file named after a region node id (`canon/art/thornbury.svg`) appears
  automatically on that node's location card in the live viewer.

## The loop

1. **Brief.** One per piece: subject (use the node's `description` from
   region.yaml when there is one), mood, canvas size, exact output path,
   and anything that must appear.
2. **Artist pass.** Dispatch the `svg-artist` agent with the brief. It
   drafts, renders, self-critiques against its own render, and iterates
   before returning. (No agent-dispatch tool available? Do the artist role
   yourself, following `.claude/agents/svg-artist.md` to the letter.)
3. **Adversarial review.** Dispatch `svg-art-reviewer` — a *fresh* agent,
   never the artist's own context — pointed at the file. It returns `PASS`
   or ranked defects.
4. **Fix round.** Defects go back to the artist (same context if possible —
   it knows the piece). Then review again. Cap at two fix rounds; if it
   still fails, keep the best version and report the open defects honestly.
5. **Done.** Final render inspected, file at its path. Report path + one
   line per piece + any defects accepted.

Batching: independent pieces run their loops in parallel — one artist and
one reviewer per piece, never shared.
