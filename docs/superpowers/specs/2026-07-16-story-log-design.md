# Story log & entity cards — design

The live viewer's story feed becomes a first-class engine artifact instead of
a filtered Claude Code transcript. Filtering a terminal log can never yield a
clean story — background-task notifications, GM meta-chatter, and setup
dialogue all leak, and each fix is a better sieve on a dirty source. The
overhaul makes noise impossible **by construction**: nothing appears in the
feed unless it was deliberately written there.

## The story log

`state/story.jsonl` — append-only, engine-written, committed with the save.
One JSON entry per line: `{"session": N, "clock": {date, hour}, "type": ...,
...payload}`. No wall-clock timestamps (deterministic, testable); the game
clock is the story's time. The viewer tails it with a byte-offset cursor,
exactly as it tailed transcripts. Raw markdown is stored; HTML is rendered
(and sanitized) at read time.

Two producers, no third:

1. **Auto-emitted** — the engine posts structured entries as side effects of
   the moments it already owns:
   - `session start` → `system` ("Session N begins")
   - `char create` → `character` card ref
   - `quest offer/accept/complete/cancel` → `quest` card ref with event
   - `encounter start/end` → `combat` marker (name; end carries xp/loot line)
   - `travel` → `system` (arrival line)
   - `level up` → `system`
   - death / `revive` → `system`
2. **Deliberately posted by the GM** (tool calls inside the one interactive
   session — never `claude -p`, never an API call):
   - `engine story narrate --text ...` — table prose (markdown)
   - `engine story scene --title ... [--subtitle ...]` — a scene header
   - `engine story choices [--title ...] --item ... --item ...` — the
     "what you can do right now" menu
   - `engine story reveal --npc id | --monster type | --pc id` — drop an
     entity card into the feed when someone is introduced
   - `engine story action --pc id --text ...` — verbatim in-character player
     speech, attributed

The Claude transcript is never read again: `story.py` and its tests are
deleted; the `/api/story` route reads the log. Operator terminal input never
auto-appears — the GM narrates player actions into prose (or posts `action`
for spoken lines).

## Entity cards

`GET /api/entity/<ref>?lens=` resolves live state into a card, lens-aware:

- `pc-*` → sheet (race/class/level, hp/ac, attributes, skills, effects,
  equipped gear, gold, features, spells) + `played_by` + bio
  (`canon/party/<id>.md`, rendered). Party is public — both lenses see all.
- encounter combatant id (`goblin-2`) → instance card. Player lens: name,
  status word, effects, bestiary description; GM lens adds hp/ac/attacks.
  A hidden monster resolves only for the GM.
- bestiary type (`goblin`) → type card (description; GM adds stats).
- `npcs.yaml` key → name/role/disposition/location (+ description if the
  game provides one); GM lens adds `wants`.
- quest id → quest card (title, status, reward, deadline; escrow internals
  GM-only).

`char create` gains `--played-by` (stored on the sheet) so cards can say who
runs the character.

Feed entries of type `character`/`npc`/`monster`/`quest` carry only the ref;
the client fetches the card, so cards are always live (HP changes, status,
level-ups). Clicking a card — or any party/roster row — opens a full card
overlay.

## Viewer rendering by type

- `narration` — the manuscript styling that already exists (unchanged).
- `scene` — a centered header card: title + subtitle rule line.
- `system` — a quiet centered milestone line between beats.
- `choices` — an action-menu card (title + items).
- `action` — the existing operator line style, attributed to the PC.
- `character`/`npc`/`monster`/`quest` — compact card chips inline in the
  feed; click to expand the overlay.

## Agent & skills

- `gm.md`: every table-facing beat is posted with `engine story narrate`
  before the turn ends; scene/choices/reveal at the natural moments;
  bookkeeping never posted. The voice rule stands.
- `gm-session`: open scenes with `story scene` + narration + choices.
- `party-create`: pass `--played-by`; the character cards emit themselves.
- `gm-combat`: post round narration; encounter cards are automatic.

## Compatibility

Old worlds have no `story.jsonl` → empty feed with the existing hero state
until the GM posts (or a `world upgrade` + new session begins one). The old
transcript-derived feed is gone, not migrated.
