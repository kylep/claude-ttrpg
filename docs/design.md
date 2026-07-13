# claude-ttrpg Design

Status: open questions resolved, ready for implementation planning
Date: 2026-07-12

## Purpose

claude-ttrpg is an engine plus tooling for running tabletop RPGs with Claude
Code. It is system-agnostic: D&D-style high fantasy and cyberpunk are both
just content. The engine handles rules execution, dice, and state tracking;
Claude handles narration, adjudication, and NPC simulation.

## Roles and modes

- **Operator**: one person runs the Claude session.
- **Players**: zero or more humans play player characters. At zero players,
  Claude simulates the party — the world can run as a pure simulation.
- **GM modes**: Claude defaults to **auto-GM** (narrates and adjudicates).
  The operator switches to **manual GM** with an explicit command; Claude
  then defers all rulings to the human and keeps doing the paperwork.
  Every manual override is recorded in the event log as an override event.

## Core principles

1. **Scripts own all game math.** Dice rolls, combat resolution, HP,
   inventory, effect durations, and every state mutation go through
   deterministic scripts. Claude never invents a number. This makes play
   auditable and cheat-proof — an LLM cannot roll dice honestly or track
   numbers reliably in context.
2. **All state lives in files**, never a database. Worlds are git repos.
3. **GM overrides are explicit.** The operator concretely tells Claude
   "GM override" — overrides are logged, never inferred.
4. **Claude-GM first, human-readable second.** Data formats are designed
   for machine execution, rendered into human-readable sheets and maps as
   a secondary output.

## What defines a Game

A game definition contains three layers.

### Ruleset (reusable across worlds)

- Core resolution mechanic — how any attempt succeeds or fails
  (die + modifier vs. difficulty, or equivalent). Combat, skill checks,
  saves, and social encounters all build on this primitive.
- Attributes
- Classes
- Races (player and monster)
- Spells / skills
- Effects (poisoned, prone, …)
- Character creation rules — attribute assignment, starting gear and level
- Level / progression mechanic
- Combat rules — turn-based: initiative, action economy (what one turn
  allows), range and movement
- Health, damage, death, and recovery — HP, dying, rests, healing
- Non-combat resolution — perception/stealth, social checks, traps, hazards
- Time structure — rounds ↔ rests ↔ travel time ↔ calendar
- Economy — currency, prices, loot tables
- Items and equipment
- Navigation mechanic — node-graph movement with travel times

### World / setting content (template in the game, instantiated per world)

- Maps and geography — node graphs; each node carries approximate
  coordinates and terrain metadata so region maps can be rendered as
  generated images
- History and setting details
- Bestiary — full monster stat blocks with difficulty ratings
- NPCs and factions — named characters, goals, relationships (required
  for NPC simulation)

### Deferred (not v1)

Languages, alignment, crafting, weather, multiclassing.

## Reference game

The template game that ships in `games/`:

- **Resolution**: d20 + modifier vs. difficulty class. Natural 20 crits,
  natural 1 fumbles.
- **Attributes**: the classic six — STR, DEX, CON, INT, WIS, CHA — with
  standard modifier scaling. Names and mechanics are not copyrightable;
  all text is written fresh.
- **Classes**: Fighter, Rogue, Cleric, Wizard — one per archetype,
  matching the v1 four-PC party.
- **Progression**: levels 1–3 authored for v1. Higher levels are additive
  content, not engine work.

Finer-grained numbers (spell lists, price tables, monster stats) are
content authoring inside `games/reference/`, not design decisions.

## Maps and movement

Two scales, each fit for purpose:

- **World/region maps** are node graphs: locations connected by routes
  with travel times. Nodes carry approximate (x, y) coordinates and
  terrain tags, which double as prompts for image generation.
- **Combat maps** are optional square grids for positioning, range, and
  movement speed during encounters.

### Combat grid representation

Encounters store grids as sparse coordinates: the encounter file declares
grid width × height, then lists combatants and terrain features each with
an (x, y). There is no cell matrix to keep in sync — distance, range, and
movement checks are arithmetic the engine owns.

```yaml
grid: {width: 12, height: 8}
terrain:
  - {type: wall, cells: [[4,0],[4,1],[4,2]]}
  - {type: difficult, cells: [[7,5],[8,5]]}
combatants:
  pc-brin:  {pos: [2, 3]}
  goblin-1: {pos: [9, 4]}
```

### Rendering

Three layers over the same grid model:

1. **ASCII** — `engine map render` prints a deterministic grid with a
   legend in the session terminal. This is the v1 contract: positions
   shown always match state.
2. **SVG** — the same render module writes stamped files
   (`renders/<in-world-date>-<encounter>-r<round>.svg`) and maintains a
   static `renders/index.html` gallery, newest first, openable from a
   chat link. `renders/` is gitignored: renders are derived artifacts,
   always regenerable from `state/` and `timeline/`.
3. **Claude narration** — Claude describes the scene on top of the
   engine's render; it is never the source of truth for positions.

## Persistence: three tiers

### Tier 1 — Games

A complete, unique set of ruleset + content. Lives in this repo under
`games/<name>/`. The reference template game ships here; a new game copies
the template or starts blank. Games are versioned.

### Tier 2 — Worlds

A world is an instance of a game — a campaign. Each world lives in its own
**private git repo**. Entities never cross worlds. A world pins the game
and version it was instantiated from, so engine or game updates never
silently mutate a running campaign.

World repo layout:

```
world.yaml          # manifest: game name + version, world name, created date
state/              # authoritative present snapshot: party, sheets,
                    #   positions, world clock, quest state
canon/              # setting, history, NPCs, factions, maps
timeline/           # append-only event log ordered by in-world date
  1203-04-17-001.yaml   # event: in-world date, session, type,
                        #   mechanical deltas, GM-override flag
sessions/           # per-session transcripts and summaries
renders/            # derived map renders + index.html gallery (gitignored)
```

`state/` is the truth for "now". `timeline/` is the audit log and
narrative canon. Scripts update both atomically; the present is never
recomputed by replaying the log.

### Tier 3 — Timelines

The timeline is the event log plus git history. Two ways to go back in
time:

**Fork** — a save-file branch. Forking at a past point is `git branch`
from that commit or tag. History after the fork point does not exist in
the new branch's ancestry; the old branch survives as its own abandoned
timeline and can be resumed later. Branches never merge (enforced by
hook). Save points are git tags.

**Insert** — a history-authoring mode on the current branch, for fleshing
out the world's past. Insert sessions append events with past in-world
dates into the same log. Predestination is enforced in two layers:

1. **Hard (scripted)**: a validator blocks mechanical contradictions with
   later canon — killing an NPC who has events after this date, destroying
   a location that exists later, acquiring a unique item someone else
   holds in the future.
2. **Soft (Claude)**: Claude loads all post-insert-point canon as
   constraints and steers the narrative to keep it intact, refusing player
   actions that would break it. This layer is best-effort; the validator
   catches the mechanical class of paradox, narrative subtleties can slip.

Insert is **lore-only**: nothing from an insert session auto-mutates
`state/`. Anything that should exist in the present (an item buried 20
years ago, a grudge, a map) is explicitly reconciled by the GM and
recorded as an override event.

Emergent property: because insert events carry in-world dates and forks
are branches, a fork inherits every insert authored before the fork
point — deep history stays shared across all timelines; only post-fork
play diverges.

## Engine interface

The engine is Python 3.12+, managed with uv, built on Typer, living in
`engine/`. It exposes a single CLI entrypoint with subcommands:

```
$ engine roll d20+5 --vs 14
{"roll": 11, "total": 16, "vs": 14, "success": true, "crit": null}

$ engine attack --attacker goblin-2 --target pc-brin
{"hit": true, "damage": 4, "target_hp": [9, 13], "events": ["1203-04-17-014"]}
```

Contract:

- Structured JSON on stdout; invalid operations return a JSON error
  object and a nonzero exit code.
- Mutating commands update `state/` and append the corresponding
  `timeline/` event atomically in one invocation.
- The engine locates its world git-style: walk up from cwd to find
  `world.yaml`. Sessions launch inside the world repo; `--world PATH`
  overrides for tooling.
- One entrypoint means one permission-allowlist entry, `--help`
  discoverability, and testability without Claude in the loop.

## Canon sync

Two mechanisms keep `canon/` current:

- **Continuous during play**: Claude updates `canon/` live as narrative
  facts land — an NPC met, a secret revealed, a faction stance shifted.
- **`session end` — the dreaming pass**: at session close, Claude
  re-reads the session's full canon diff (session-start commit → now)
  plus the transcript, then autonomously: (1) writes a structured
  summary into `sessions/`, (2) reconciles contradictions and plot
  holes introduced during play — fixing directly and reporting what
  changed, escalating to the operator only when a fix would alter
  something load-bearing, (3) prunes low-value detail that will never
  matter again. The pass concludes with a single git commit — the
  formal session boundary. Anything pruned or rewritten remains
  recoverable in git history.

Dreaming touches `canon/` and `sessions/` only. `timeline/` is
append-only audit and is never pruned; `state/` is engine-owned. Claude
curates narrative memory; the mechanical record stays untouchable.

## Claude integration

Sessions launch with a dedicated agent (`claude --agent gm` or similar)
whose skillset is purpose-built and constrained — the operator's base
skills are not loaded. Planned skills cover: session start/resume, combat
running, character creation, world instantiation from a game, insert-mode
play, fork/save management, and GM override handling.

Prior art worth borrowing: Blades in the Dark's flashback mechanic uses
the same rule as Insert — flashbacks add to history but cannot contradict
established facts.

## v1 milestone

One short full adventure, end to end: town → travel → dungeon → boss,
with rests, loot, leveling, and NPC dialogue. Real dice via scripts,
state persisting to a world repo, playable in auto-GM mode with manual
override available. Four player characters, 0 to 4 played as humans.

## Open questions

None currently. Resolved 2026-07-12: reference game contents (see
"Reference game"), engine language and CLI contract ("Engine
interface"), combat grid representation and rendering ("Maps and
movement"), and transcript→canon flow ("Canon sync"). Exact CLI
subcommand inventory and ruleset numbers land in `docs/dev/` and
`games/reference/` during implementation.
