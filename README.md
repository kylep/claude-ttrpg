# claude-ttrpg

Engine, scripts, and Claude Code skills for running tabletop RPGs.

The engine is system-agnostic: a **Game** defines a complete ruleset and
content set (classes, races, items, spells, combat rules, …), a **World**
is a playable instance of a game living in its own private git repo, and
**Timelines** let a world fork like save files or backfill its own history.

Claude acts as game master (with an explicit human-GM override mode),
narrating and adjudicating while deterministic scripts own every dice roll,
stat, and state mutation.

v1 is playable: engine, reference game, and GM agent are implemented.
Insert-mode and fork-management tooling are post-v1 (see the design doc).

## Install

Install the engine CLI with [uv](https://docs.astral.sh/uv/):

```bash
uv tool install --editable ./engine
```

The editable install picks up code changes automatically but not new
dependencies — after pulling a change that adds one, rerun with
`--reinstall`.

Then create a world and start playing — see the [playing
guide](docs/playing.md).

## Documentation

- **[Playing](docs/playing.md)** — create a world, run your first session,
  steer the GM, and what the engine enforces in play.
- **[Tools](docs/tools.md)** — the live web table view (`engine serve`),
  printable handbooks (`engine export`), and image generation.
- **[Worlds are git repos](docs/worlds-and-git.md)** — saves, forks, and
  time travel; how a world's files map to git.
- **[Design](docs/design.md)** — the design document: goals, roles, tiers,
  and open questions. Start here to understand the system.
- **[docs/dev/](docs/dev/)** — implementation planning, the post-v1
  backlog, and design/review notes.

## Repository layout

- `games/` — game definitions, including the reference template game
- `engine/` — the `engine` CLI: game logic and world-state mutation
- `.claude/` — agents and skills for GM sessions
- `tools/` — standalone utilities (e.g. image generation)
- `docs/` — documentation (see above)
