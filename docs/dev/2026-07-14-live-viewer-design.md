# Live world viewer — `engine serve` (2026-07-14)

Approved design from the brainstorming session; built the same day.

## Problem

Following play through Claude's terminal output is a poor reading
experience, SVG battle maps are awkward to open, and there is no way to
share the game with someone not driving the terminal. Wanted: a locally
hosted, live-reloading web view over the world's asset files. The
terminal remains the only input surface.

## Decisions (settled with the operator)

- **Audience: both lenses.** `/` is player-safe, `/gm` shows everything.
- **Story source: parse Claude Code session transcripts** (the
  `~/.claude/projects/<sanitized-world-cwd>/*.jsonl` files). Fully
  automatic — no GM discipline in the loop. Accepted trade-off: couples
  the story pane (only) to Claude Code's log format; quarantined in one
  module with graceful degradation.
- **Stack: stdlib only** (`http.server` + Server-Sent Events, vanilla
  embedded page). No new dependencies, matching repo policy.
- **Live map** is rendered server-side from *current* encounter state
  via the existing `render.svg_map`, not from the round-stamped
  `renders/` snapshots.

## Architecture

New engine modules; the server is strictly read-only over world files
(it never writes `state/`, `timeline/`, or anything else — including
avoiding `quests.list_quests`, whose deadline-expiry side effect writes;
the viewer reads `state/quests/*.yaml` raw).

### `story.py` — transcript feed

- `project_dir_for(world_root)` — `~/.claude/projects/` +
  `re.sub(r'[^A-Za-z0-9-]', '-', str(world_root))`; verified by reading
  a `cwd` field from a record in the newest transcript; on mismatch,
  scan project dirs for one whose newest transcript's `cwd` matches.
- `read_story(world_root, cursor) -> (entries, cursor)` — tails the
  newest `.jsonl` by mtime (switches files when a newer session starts;
  cursor is `{"file": name, "offset": bytes}`). Yields
  `{"role": "operator"|"gm", "html": str}`:
  - `type: user` records with plain-string or text-part content →
    operator entries; skip tool-result content, `<command-name>`
    local-command records, and strip `<system-reminder>`/
    `<local-command-*>` blocks; skip if empty after stripping.
  - `type: assistant` → concatenated `text` parts (tool_use/thinking
    skipped); skip API-error placeholder texts.
  - Everything else skipped. Unparseable lines skipped (never fatal).
- Markdown rendered server-side with export's `_md()` (markdown +
  script-stripping hardening) — model/user text is untrusted.

### `viewer_data.py` — lens snapshots

`state_snapshot(root, g, lens) -> dict` with keys: `world`, `clock`,
`location`, `party` (full sheets — players own their sheets), `quests`
(raw quest files), `encounter` (roster payload or `None`), `map_svg`
(from `render.svg_map`), and — GM lens only — `timeline` (last ~30
events by filename order) plus raw encounter internals.

Player-lens encounter filtering (pure function, unit-tested):
- monsters with the `hidden` effect are removed from the roster and
  from the copy of the encounter given to `svg_map`;
- monster `hp`/`max_hp` replaced by a status word: `healthy` (>2/3),
  `wounded` (>1/3), `bloodied` (rest), `down` (dead);
- `stealth`, `sneak_used`, `grapples`, `gear_actions` keys dropped;
- PCs pass through whole (including hidden PCs — the players know).

### `serve.py` — HTTP server

`engine serve [--port 8787]`, binds `127.0.0.1` only.

- `GET /` and `GET /gm` → the embedded page (lens from path).
- `GET /api/state?lens=player|gm` → `state_snapshot` JSON.
- `GET /api/story?file=&offset=` → incremental story entries + cursor.
- `GET /events` → SSE. Each connection polls mtimes itself (~300ms)
  over `state/`, `timeline/`, `renders/`, and the transcript file;
  emits `state` / `story` named events (empty data) plus keepalive
  comments. Client disconnects (BrokenPipe) handled quietly.
- `GET /renders/<name>` → static file, resolved path must stay inside
  `renders/` (traversal rejected).
- No POST routes. `ThreadingHTTPServer`, daemon threads.

### `viewer.html` — the page

Package data (`importlib.resources`), self-contained vanilla JS/CSS,
dark theme. Story feed is the main column (auto-scroll, operator vs GM
entries styled distinctly); live map beside it; party bar with HP bars
and effect chips; sidebar with clock, location, quests; GM lens adds
the timeline tail and raw encounter details. `EventSource` on
`/events`; `state` tick → refetch snapshot, `story` tick → refetch
story from cursor.

## Failure posture

Panes degrade independently: no transcript dir / unrecognized format →
story pane shows "no live session feed", everything else works; no
encounter → map pane shows location + date; port busy → clear error
suggesting `--port`.

## Testing

- Unit: lens filters (hidden monster gone, HP words, no
  stealth/grapples leakage, GM lens unfiltered); story parser against
  fixture JSONL (operator/GM entries, skipped noise, malformed lines,
  cursor increments, session-file switch).
- Server: start on an ephemeral port in-test; assert `/api/state` lens
  differences, `/api/story` shape, `/events` first bytes + tick after
  a state write, `/renders` traversal rejection, `/` and `/gm` serve
  the page.
- Reference e2e: init a world from `games/reference`, start an
  encounter, hide a monster, assert the player snapshot omits it while
  `/gm` shows it.

## Non-goals (v1)

Browser input, auth, non-localhost binding, session-history browsing,
multi-world, websockets, JS frameworks/build steps, showing per-roll
dice in the player lens beyond what narration says.

## Follow-ups (backlog candidates)

- aloft/prone/hidden badges on the SVG map tokens
- session-history browsing in the viewer
- gm-session skill autostarting the server
