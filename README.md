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

Create a world — either ask Claude to use the `world-new` skill, or
run it directly:

```bash
engine world init <dir> --game games/reference --name "<name>"
```

Launch the GM from inside the world repo:

```bash
cd <world> && claude --agent gm
```

Three phrases steer the operator relationship with the GM at any time:

- **"GM override"** — apply an instruction as-is; it gets logged to
  the timeline.
- **"manual GM"** — every ruling (DCs, NPC reactions) is deferred to
  you; the engine paperwork keeps happening automatically.
- **"auto GM"** — hand rulings back to Claude.

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

**Inserting history (backfilling the past).** The design also supports
*insert-mode* play: sessions set in the world's past that append events
with earlier in-world dates — fleshing out backstory the way a
flashback does. Inserts are lore-only (they never auto-change
`state/`), and predestination is enforced so the past can't contradict
established canon: a scripted validator blocks mechanical paradoxes
(killing an NPC who demonstrably lives later), and the GM steers the
narrative around softer ones. Because events carry in-world dates,
anything inserted before a fork point is inherited by every timeline
forked after it. The insert-mode tooling (validator + skill) is
post-v1 and not yet built — today the GM can backfill lore by editing
`canon/` during play, and the session-end pass reconciles it; see
`docs/design.md` (Tier 3 — Timelines) for the full design.

## Status

v1 playable: engine, reference game, and GM agent are implemented (see
the Playing section). Insert-mode and fork-management tooling are
post-v1; see `docs/design.md`.
