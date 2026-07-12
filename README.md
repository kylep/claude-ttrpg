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

## Status

Design phase. See `docs/design.md`.
