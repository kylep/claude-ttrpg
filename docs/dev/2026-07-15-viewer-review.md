# Live viewer review + improvement backlog (2026-07-15)

Playtest review of `engine serve` (the `/` player lens and `/gm` GM lens)
against a copy of a real world (`test1`) with a rich encounter running
(hidden goblin, wounded goblin, poisoned archer, prone + frightened PCs)
and a populated story feed from a real Claude Code transcript.

Method: drove both lenses in headless Chromium (Playwright) at desktop
(1400px) and mobile (390px), empty-story and populated-story states;
confirmed live SSE reload end-to-end (DOM updated 446ms after an engine
state write, no page reload); read `render.svg_map`, `viewer.html`,
`viewer_data.py`, `story.py`, `serve.py`.

What already works well and must not regress: two lenses with correct
hidden-monster masking (player map/roster never show the hidden goblin;
monster HP shown as words, not numbers), markdown story rendering with
tables/lists, player lens strips fenced `<pre>` blocks, SSE live reload,
XSS-escaped author content, graceful empty states (no JS errors on any
lens/width), reduced-motion + focus-visible baseline.

## Priorities

Legend: **P0** usability/correctness, low risk · **P1** high-value
feature/visual · **P2** polish.

### P0 — the map and layout

- [ ] **Rail is not sticky (desktop).** `.table` is a plain grid; the
  `<aside>` scrolls with the page, so the map slides out of view the
  moment you scroll the story. During combat you lose the battlefield
  while reading narration. Make the rail `position: sticky; top:<header>`
  with its own overflow, so the map stays pinned. `viewer.html` `.table`
  / `aside`.
- [ ] **Mobile buries the map.** Single-column stack puts the tall story
  column first and the map/rail dead last — on a phone you scroll past
  the entire session log to see the battle. Re-order so the map/rail
  comes first (or is reachable) on narrow widths, at least while an
  encounter is active. `viewer.html` grid order + media query.
- [ ] **SVG legend clips off the right edge.** The bottom caption
  (`name — round N — g=… K=pc-luca[s]`) is one line at `x=4`, wider than
  the SVG viewBox, so it's cut off in every map (`pc-luca` truncated).
  `render.svg_map` render.py:81-82.

### P0 — chrome polish

- [ ] **Raw lowercase location id.** Header shows `thornbury`, not
  `Thornbury`. Title-case the location (and ideally resolve region-node
  display names). `viewer.html` `renderState` / `viewer_data`.
- [ ] **GM internals is a raw JSON dump.** `{"stealth": {}, ...}` —
  mostly-empty debug object, ugly and low-signal. Hide the card when all
  keys are empty; when populated, render as readable rows, not
  `JSON.stringify`. `viewer.html` `#internals`.
- [ ] **No positive liveness signal.** There's an "offline" line on
  error but nothing that says it's live and updating. Add a small "live"
  pulse in the header that flashes on each SSE tick, so the operator
  trusts the auto-refresh. `viewer.html` header + `connect()`.

### P1 — the battle map is the product

- [ ] **Tokens carry no status.** A prone / poisoned / hidden / bloodied
  / aloft token looks identical to a healthy one — all are plain colored
  circles with a letter. Add: a colored HP ring (green/gold/red by
  fraction), a badge/glyph for aloft + prone + hidden, and dim/strike
  dead tokens. This enriches the exported round-stamped SVGs too (shared
  `svg_map`). render.py `svg_map`.
- [ ] **Whose turn is invisible on the map.** `up` is named only in the
  text line. Highlight the active combatant's token (glow/outline) and
  its roster row. `svg_map` + `viewer.html`.
- [ ] **Token identity is a guessing game.** K/O/L/M/g/h/i decode only
  via the tiny (clipped) caption. Render an HTML token legend in the rail
  (swatch + letter + name), and drop the redundant SVG caption for the
  viewer (keep it for standalone/exported SVGs via a `caption=` flag).
  Removes the duplicate encounter-name line too.
- [ ] **Gold and stash are computed but never shown.** `state_snapshot`
  returns `party_gold` and `stash`; nothing renders them. Add a party
  purse/stash line (GM sees gold always; decide player visibility).
  `viewer.html`.

### P1 — the empty state is the first impression

- [ ] **Empty story = black void.** With no matched session the left
  ~60% is dead space and one italic line while everything crams into the
  right rail. Turn the empty story column into a title/hero: world name,
  location + clock, the party as a portrait/medallion row, and the
  "start a session" hint framed as a call to action — not an apology.
  `viewer.html` `#story-empty`.

### P2 — polish

- [ ] **Story beats have no timestamps.** Can't tell pacing. Optional
  timestamp per beat (from the transcript record time).
- [ ] **Party card could be richer.** AC shield, an initial medallion,
  clearer level. Small.
- [ ] **Combat-forward layout.** Consider swapping emphasis when an
  encounter is active (map-forward) vs exploration (story-forward).
  Larger change; defer.

## Constraints / notes for the implementer

- `render.svg_map` is shared by the live viewer (`innerHTML`), by
  `write_svg` (round-stamped `renders/*.svg` + `renders/index.html`), and
  by exports. Any token/caption change must keep those working — the
  standalone SVGs still need an embedded caption/legend, so gate the
  caption behind a param rather than deleting it. Tests:
  `test_serve.py`, `test_render*.py`, export tests.
- The viewer is strictly read-only and must never write world state
  (`viewer_data` already reads quests raw to avoid the expiry side
  effect). Keep it that way.
- Author-controlled strings reach the SVG and the story HTML — keep the
  existing escaping (`test_map_svg_escapes_author_name_against_xss` must
  stay green).
- `networkidle` never fires (SSE stays open) — not a bug, but automated
  drivers must wait on `load`, not idle.
