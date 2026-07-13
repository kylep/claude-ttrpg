# ky-ttrpg

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

## Status

Design phase. See `docs/design.md`.
