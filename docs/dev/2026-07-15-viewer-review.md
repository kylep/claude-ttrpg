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

- [x] **Rail is not sticky (desktop).** ~~scrolls away.~~ → `aside` is
  now `position: sticky; top: 3.4rem` with its own `overflow-y` and a
  `max-height` of the viewport; the map stays pinned while the story
  scrolls (verified: after scrolling story to 1600px, map card sits at
  `top: 54`, in view). `viewer.html` `.table` / `aside`.
- [x] **Mobile buries the map.** ~~map dead last.~~ → on ≤900px the rail
  gets `order: 1` and `main` `order: 2`, so the map/rail leads and the
  story follows (verified on the 390px shot). `viewer.html` media query.
- [x] **SVG legend clips off the right edge.** ~~one line, truncated.~~
  → `_caption_lines` wraps the caption to the map width and grows the SVG
  height per line; the live viewer drops the caption entirely
  (`caption=False`) and renders an HTML legend instead. render.py.

### P0 — chrome polish

- [x] **Raw lowercase location id.** ~~`thornbury`~~ → title-cased in
  `state_snapshot` (`Thornbury`). viewer_data.py.
- [x] **GM internals is a raw JSON dump.** ~~mostly-empty blob~~ → the
  card hides itself when every bucket is empty, and renders readable
  `key → value` rows when populated. `viewer.html` `renderInternals`.
- [x] **No positive liveness signal.** → a health-green pulse dot in the
  header flashes on each SSE state/story tick and turns blood-red on
  disconnect. `viewer.html` `beat()` / `connect()`.

### P1 — the battle map is the product

- [x] **Tokens carry no status.** → tokens now get a health-banded ring
  (moss/gold/blood), a red warning pip for any bad condition, a dashed
  ring + `?` for hidden, and an aloft caret. Dead still leave the board.
  Health rings reach player-lens monsters via the status-word band, and
  enrich exported SVGs too. render.py `svg_map` + `_token_status`.
- [x] **Whose turn is invisible on the map.** → the active combatant's
  cell is tinted + outlined ember on the map, and its roster row and
  legend entry are highlighted to match. `svg_map` + `viewer.html`.
- [x] **Token identity is a guessing game.** → an HTML legend under the
  map (coloured swatch + glyph + name, active one emphasised); the
  redundant SVG caption is off for the viewer. viewer_data + viewer.html.
- [x] **Gold and stash are computed but never shown.** → a purse line
  under the party card (`N gp · M in stash`). `viewer.html` `renderPurse`.

### P1 — the empty state is the first impression

- [x] **Empty story = black void.** → the empty story column is now a
  title card: world name, location · clock, a party medallion row, and
  the "start a session" line as a call to action. `viewer.html`
  `buildHero`.

### P2 — polish

- [ ] **Story beats have no timestamps.** Can't tell pacing. Optional
  timestamp per beat (from the transcript record time).
- [x] **Party card could be richer.** → AC shield (⛊ N) now shows on
  party rows and, GM-lens, foe rows; medallions already appear on the
  empty-state hero. `viewer.html` `hpBar` + viewer_data `_roster`.
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
