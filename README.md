# claude-ttrpg

Engine, scripts, and Claude Code skills for running tabletop RPGs.

The engine is system-agnostic: a **Game** defines a complete ruleset and
content set (classes, races, items, spells, combat rules, …), a **World**
is a playable instance of a game living in its own private git repo, and
**Timelines** let a world fork like save files or backfill its own history.

Claude acts as game master (with an explicit human-GM override mode),
narrating and adjudicating while deterministic scripts own every dice
roll, stat, and state mutation.

## Layout

- `docs/design.md` — the design document (start here)
- `docs/dev/` — implementation planning
- `games/` — game definitions, including the reference template game
- `engine/` — scripts that run game logic and mutate world state
- `.claude/` — agents and skills for GM sessions

## Playing

Install the engine CLI:

```bash
uv tool install --editable ./engine
```

Create a world — either ask Claude to use the `world-new` skill (which
does all of the below for you), or by hand:

```bash
# init writes the world files into a new directory
engine world init ~/ttrpg/saves/world1 \
  --game ~/gh/claude-ttrpg/games/reference --name "World One"

# install the GM agent + skills into the world (claude loads .claude/
# from the directory you launch it in)
cp -r ~/gh/claude-ttrpg/.claude ~/ttrpg/saves/world1/.claude

# make it a git repo: the commit is save zero, the tag a named restore point
cd ~/ttrpg/saves/world1
git init
git add -A && git commit -m "world created: World One"
git tag genesis

# play — the GM commits automatically at every session boundary from here
claude --agent gm
```

(`--game` takes any path to a game directory; use the absolute path
unless you're running from inside this repo.)

Three phrases steer the operator relationship with the GM at any time:

- **"GM override"** — apply an instruction as-is; it gets logged to
  the timeline.
- **"manual GM"** — every ruling (DCs, NPC reactions) is deferred to
  you; the engine paperwork keeps happening automatically.
- **"auto GM"** — hand rulings back to Claude.

Gear is live state: `engine equip` / `engine unequip` recompute AC and
attacks from what's actually worn, magic items carry boons (and
sometimes curses — `engine item dispel` is the remedy), and the party
can split: `travel`, `encounter start`, and `rest` all take `--pcs` to
act on a subset, with XP flowing only to the PCs who were actually in
the fight. Quests are first-class state too (`engine quest
offer/accept/complete/cancel/list`): NPC and PC rewards are escrowed up
front — no vaporware bounties — while world quests can spawn rewards
and grant XP. Thornbury's quest board ships with two.

### Printable handbooks

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

## Worlds are git repos — saves, forks, and time travel

A world's entire save state is files in its own git repo, so git *is*
the save system:

```
world.yaml   # which game + version this world was created from
state/       # the present: party, character sheets, positions, clock
canon/       # narrative truth: setting, history, NPCs, factions, maps
timeline/    # append-only event log — every roll's outcome, every
             #   mutation, one file per event, ordered by in-world date
sessions/    # per-session transcripts and summaries
```

`state/` is authoritative for "now"; `timeline/` is the audit trail and
the story's mechanical record. Only the engine writes to either — the GM
narrates from engine output and edits `canon/` for narrative facts.

**Saving.** The GM skills commit at every session boundary (`session NNN
start`, `session NNN: <summary>`), so each session is a save point out
of the box. For a named save you can return to, tag it:

```bash
git tag before-the-tomb
```

**Loading / forking.** Rewinding is branching. A fork is a full
alternate timeline — the original keeps existing and can be resumed:

```bash
git branch tomb-attempt-2 before-the-tomb   # fork from the save point
git checkout tomb-attempt-2                  # play the alternate line
```

Timeline branches never merge — two presents can't be reconciled into
one. Deep history is naturally shared: everything authored before the
fork point exists in both lines' ancestry.

**Inserting history (backfilling the past).** An *insert* is a session
set in the world's past — a flashback that fleshes out backstory
without touching the present. Two rules make inserts safe: they are
**lore-only** (nothing an insert session does auto-changes `state/` —
the present's HP, inventory, and positions stay untouched), and they
must respect **predestination** (the past can't contradict established
canon: an NPC alive today can't die in your flashback).

To run one today, tell the GM at a session start:

> "This session is an insert — a flashback set 20 years before the
> campaign, when Halda first came to Thornbury."

The GM then plays the scene normally (dice and checks still go through
the engine) but records the outcomes as narrative history in `canon/`
(history.md, NPC entries) instead of mutating the present. If something
from the flashback *should* exist in the present — a buried item, a
debt, a grudge — you apply it explicitly: say "GM override" and the
change lands through engine commands with a logged override event.
Because canon lives in git, an insert committed before a fork point is
inherited by every timeline forked after it — deep history stays shared.

First-class insert tooling is post-v1 and not yet built: dated
`timeline/` events for insert sessions and a validator that mechanically
blocks paradoxes (see `docs/design.md`, Tier 3 — Timelines). Until
then, predestination is enforced only by the GM's discipline plus the
session-end reconciliation pass.

## Status

v1 playable: engine, reference game, and GM agent are implemented (see
the Playing section). Insert-mode and fork-management tooling are
post-v1; see `docs/design.md`.
