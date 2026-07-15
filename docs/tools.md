# Tools

Auxiliary tooling around a world: a live web view, printable handbooks, and
image generation.

## Live table view

`engine serve` (run inside a world; default port 8787) hosts a local,
read-only web view that updates live as you play — the story feed (your
prompts and the GM's narration, recovered from the Claude session itself,
none of the tool noise), a live battle map that moves when tokens move,
party HP and effects, and the quest board. `/` is the player-safe lens:
hidden monsters are actually hidden (tokens, legend, turn order), monster
health shows as words instead of numbers. `/gm` shows everything, plus the
timeline and engine internals. The terminal stays the only way to *act* —
the browser is the good reading surface, for you or for whoever's following
along.

## Printable handbooks

`engine export game|world|campaign` renders self-contained, print-friendly
HTML — a game handbook (rules, classes, races, spells, items, bestiary), a
world guide (setting, history, region map, factions, NPCs), and a campaign
book (adventure outline, quest board, and, inside a world, the live quest
list). Run them inside a world (uses `canon/` and the pinned game) or
repo-side with `--game games/reference` (no world needed); files land in
`./exports/` by default. The `export-docs` skill runs all three and, if
`gws` is installed and authenticated, uploads them as Google Docs;
otherwise it falls back gracefully and hands you the local HTML files —
handy for a printout your kid can actually read.

## Generating images

`tools/imagegen.py` is a standalone `uv` script (stdlib only, no extra
dependencies) that calls OpenAI or Gemini image models to illustrate
handbooks, world guides, and bestiary/NPC art. Set up once:

```bash
cp .env.sample .env
# then edit .env and add OPENAI_API_KEY and/or GEMINI_API_KEY
```

Generate an image:

```bash
uv run tools/imagegen.py --prompt "a weathered stone gate, painterly fantasy art" \
  --out games/reference/content/art/gate.png
```

The provider is selected via `IMAGE_MODEL` in `.env` (default `openai`,
model `gpt-image-1.5`), overridable per-run with `--model gemini`
(`gemini-3-pro-image-preview`) or `--model gemini-2.5-flash`
(`gemini-2.5-flash-image`). Generate several images in one invocation with
repeated `--prompt`/`--out` pairs, or `--batch prompts.json` (a JSON list
of `{"prompt": ..., "out": ...}` objects).

**Spend controls are on by default.** `IMAGEGEN_MAX_PER_RUN` (default 1)
caps how many images one invocation can generate; `IMAGEGEN_SPEND_CAP_USD`
(default $5.00) refuses to run once cumulative estimated spend — tracked in
the gitignored `.imagegen-ledger.json` — would exceed the cap. Both env
vars live in `.env`. Costs are rough per-image *estimates*, not real
billing data; check current spend anytime with:

```bash
uv run tools/imagegen.py --ledger-status
```

Generated art has no single fixed home — point `--out` wherever fits: a
game's own `content/art/` (e.g. `games/reference/content/art/`) for
reusable game art, or a world's `renders/` for world-specific
illustrations. The `image-gen` skill drives this tool end-to-end (prompt
composition with a consistent art style, running it, placing output, and
reporting spend) — ask Claude to illustrate something rather than invoking
the script by hand.
