# ky-ttrpg v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A playable v1: one short adventure (town → travel → dungeon → boss) run by Claude as GM, with every dice roll and state mutation owned by a deterministic Python CLI persisting to a world git repo.

**Architecture:** A single Typer CLI (`engine`) in `engine/` exposes subcommands that read/write YAML files in a world repo (discovered git-style from cwd). Pure-logic modules (dice, combat, travel…) are imported by a thin `cli.py`; every mutating command updates `state/` and appends a `timeline/` event in the same invocation. Game definitions live in `games/reference/`; Claude-facing behavior lives in `.claude/` agents and skills that call the engine and never do math themselves.

**Tech Stack:** Python 3.12+, uv (project + tool install), Typer, PyYAML, pytest (with `typer.testing.CliRunner`).

## Global Constraints

- Python `>=3.12`; dependencies limited to `typer` and `pyyaml` (dev: `pytest`). Managed by uv.
- Engine lives in `engine/`, installed entrypoint named `engine` (`[project.scripts]`).
- Every command prints exactly one JSON object to stdout. Errors print `{"error": {"code": ..., "message": ...}}` and exit 1.
- Every state file write goes through temp-file + `os.replace` (atomic per file). Mutating commands write `state/` and append the `timeline/` event in the same invocation.
- Commands that only read or roll (e.g. `roll`, `check`, `state get`, `map render`) do NOT append timeline events; only mutations do.
- All YAML via `yaml.safe_load` / `yaml.safe_dump(sort_keys=False, allow_unicode=True)`.
- RNG is a single `random.Random` seeded by the root `--seed` option (tests always pass `--seed`).
- Calendar convention: 12 months × 30 days, 24-hour days. Dates are strings `YYYY-MM-DD` (always coerce YAML dates with `str()`).
- Reference-game text is written fresh — mechanics may resemble d20 convention (not copyrightable), prose must not copy any published book.
- TDD: every engine task writes the failing test first. Commit at the end of every task (and mid-task where marked).
- Run tests from `engine/`: `uv run pytest -q`.

## File Structure

```
engine/
  pyproject.toml
  src/ttrpg_engine/
    __init__.py
    cli.py          # Typer app, emit/fail helpers, all command registrations
    errors.py       # EngineError
    dice.py         # dice expression parse + roll
    worldfs.py      # world discovery, YAML read/write, world init
    game.py         # game definition load + validate
    timeline.py     # event id allocation + append
    clock.py        # calendar arithmetic
    chargen.py      # character creation, derived stats
    checks.py       # d20 checks vs DC
    grid.py         # sparse grid math (distance, bounds, occupancy)
    combat.py       # encounter lifecycle, attack/damage/heal, movement, death
    spells.py       # spellcasting
    render.py       # ASCII + SVG renderers, renders/index.html
    rest.py         # short/long rest
    travel.py       # node-graph travel
    level.py        # xp grants, level-up
    inventory.py    # items and gold
  tests/
    conftest.py
    fixtures/minigame/   # tiny complete game used by unit tests
    test_dice.py test_game.py test_world.py test_timeline.py
    test_chargen.py test_checks.py test_grid_render.py test_svg.py
    test_encounter.py test_attack.py test_move.py test_spells.py
    test_rest.py test_travel.py test_inventory.py test_level.py
    test_e2e.py
games/reference/    # the reference game (Task 17-18)
.claude/
  agents/gm.md
  skills/gm-session/SKILL.md
  skills/gm-combat/SKILL.md
  skills/gm-override/SKILL.md
  skills/session-end/SKILL.md
  skills/world-new/SKILL.md
```

Key schemas (authoritative for all tasks):

**Character sheet** `state/party/pc-<slug>.yaml`:

```yaml
id: pc-brin
name: Brin
class: rogue
race: human
level: 1
xp: 0
attributes: {STR: 10, DEX: 15, CON: 12, INT: 13, WIS: 14, CHA: 8}
max_hp: 9
hp: 9
ac: 13
speed: 6
proficiency: 2
skills: [stealth, perception, deception]
attacks: [{name: dagger, attack_mod: 4, damage: 1d4+2, range: 1}]
spells_known: []
spell_slots: {}        # {level: {max: N, current: N}}
features: []
inventory: [{item: dagger, qty: 2}, {item: leather_armor, qty: 1}]
gold: 15
effects: []            # [{name: poisoned, duration: 3}]  duration in rounds; -1 = until cleared
```

**Party** `state/party.yaml`: `{members: [pc-brin, ...], location: thornbury, gold: 0, stash: []}`

**Clock** `state/clock.yaml`: `{date: "1203-04-17", hour: 9}`

**Session** `state/session.yaml`: `{current: 0}`

**Encounter** `state/encounter.yaml` (exists only during combat):

```yaml
id: goblin-ambush
name: Goblin Ambush
round: 1
turn: 0                # index into order
order: [pc-brin, goblin-1]
grid: {width: 12, height: 8}
terrain:
  - {type: wall, cells: [[4, 0], [4, 1]]}
  - {type: difficult, cells: [[7, 5]]}
positions: {pc-brin: [2, 3], goblin-1: [9, 4]}
monsters:              # instances; PCs stay in their sheets
  goblin-1: {type: goblin, name: Goblin 1, ac: 13, hp: 7, max_hp: 7, speed: 6,
             attributes: {STR: 8, DEX: 14, CON: 10, INT: 10, WIS: 8, CHA: 8},
             attacks: [{name: scimitar, attack_mod: 4, damage: 1d6+2, range: 1}],
             xp: 50, loot: {gold: 1d6, items: []}, effects: [], dead: false}
```

**Timeline event** `timeline/<date>-<seq>.yaml`:

```yaml
id: 1203-04-17-014
session: 3
type: attack        # attack|damage|heal|cast|death|deathsave|character|encounter|move|effect|rest|travel|level|xp|item|gold|session|override
date: "1203-04-17"
hour: 14
actors: [goblin-2, pc-brin]
summary: "goblin-2 hits Brin with scimitar for 4"
delta: {pc-brin: {hp: [13, 9]}}
override: false
```

---

### Task 1: Engine scaffold + dice roller (`engine roll`)

**Files:**
- Create: `engine/pyproject.toml`, `engine/src/ttrpg_engine/__init__.py`, `engine/src/ttrpg_engine/errors.py`, `engine/src/ttrpg_engine/cli.py`, `engine/src/ttrpg_engine/dice.py`
- Test: `engine/tests/test_dice.py`
- Modify: `.gitignore` (repo root; create if absent)

**Interfaces:**
- Consumes: nothing (first task).
- Produces: `dice.parse(expr: str) -> tuple[int, int, int]` (count, sides, modifier); `dice.roll(expr: str, rng: random.Random) -> RollResult` (dataclass: `expr, rolls: list[int], modifier: int, total: int`); `cli.app` (Typer), `cli.rng` (module-level `random.Random`), `cli.emit(payload: dict)`, `cli.fail(code: str, message: str)` (prints error JSON, raises `typer.Exit(1)`); `errors.EngineError(code, message)`. Root option `--seed`. Command `engine roll EXPR [--vs N] [--adv|--dis]`.

- [ ] **Step 1: Scaffold the uv project**

```bash
cd /Users/kp/gh/ky-ttrpg/engine 2>/dev/null || (mkdir -p /Users/kp/gh/ky-ttrpg/engine && cd /Users/kp/gh/ky-ttrpg/engine)
uv init --package --name ttrpg-engine --python 3.12
uv add typer pyyaml
uv add --dev pytest
```

Then edit `engine/pyproject.toml` so it contains (keep uv-generated build-system):

```toml
[project]
name = "ttrpg-engine"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["typer>=0.12", "pyyaml>=6"]

[project.scripts]
engine = "ttrpg_engine.cli:app"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

Append to repo-root `.gitignore`:

```
__pycache__/
*.egg-info/
.venv/
.pytest_cache/
```

- [ ] **Step 2: Write the failing tests**

`engine/tests/test_dice.py`:

```python
import json
import random

import pytest
from typer.testing import CliRunner

from ttrpg_engine import dice
from ttrpg_engine.cli import app

runner = CliRunner()


def test_parse():
    assert dice.parse("2d6+3") == (2, 6, 3)
    assert dice.parse("d20") == (1, 20, 0)
    assert dice.parse("1d8-1") == (1, 8, -1)


@pytest.mark.parametrize("bad", ["", "d", "0d6", "2d1", "1d6+", "banana"])
def test_parse_rejects(bad):
    with pytest.raises(ValueError):
        dice.parse(bad)


def test_roll_bounds():
    rng = random.Random(1)
    r = dice.roll("4d6+2", rng)
    assert len(r.rolls) == 4
    assert all(1 <= x <= 6 for x in r.rolls)
    assert r.total == sum(r.rolls) + 2


def test_cli_roll_vs():
    res = runner.invoke(app, ["--seed", "7", "roll", "d20+5", "--vs", "14"])
    assert res.exit_code == 0
    data = json.loads(res.stdout)
    assert data["total"] == data["rolls"][0] + 5
    assert data["success"] == (data["total"] >= 14)
    assert data["crit"] in (None, "hit", "fumble")


def test_cli_roll_bad_expr_is_json_error():
    res = runner.invoke(app, ["roll", "banana"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "bad_expr"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd engine && uv run pytest -q`
Expected: FAIL — `ModuleNotFoundError: ttrpg_engine.dice` (or import errors).

- [ ] **Step 4: Implement**

`engine/src/ttrpg_engine/errors.py`:

```python
class EngineError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message
```

`engine/src/ttrpg_engine/dice.py`:

```python
import re
from dataclasses import dataclass
from random import Random

_DICE_RE = re.compile(r"^(\d*)d(\d+)([+-]\d+)?$")


@dataclass
class RollResult:
    expr: str
    rolls: list[int]
    modifier: int
    total: int


def parse(expr: str) -> tuple[int, int, int]:
    m = _DICE_RE.match(expr.strip().lower())
    if not m:
        raise ValueError(f"invalid dice expression: {expr!r}")
    count = int(m.group(1) or 1)
    sides = int(m.group(2))
    modifier = int(m.group(3) or 0)
    if count < 1 or sides < 2:
        raise ValueError(f"invalid dice expression: {expr!r}")
    return count, sides, modifier


def roll(expr: str, rng: Random) -> RollResult:
    count, sides, modifier = parse(expr)
    rolls = [rng.randint(1, sides) for _ in range(count)]
    return RollResult(expr, rolls, modifier, sum(rolls) + modifier)
```

`engine/src/ttrpg_engine/cli.py`:

```python
import json
import random

import typer

from ttrpg_engine import dice
from ttrpg_engine.errors import EngineError

app = typer.Typer(add_completion=False, no_args_is_help=True)
rng = random.Random()


@app.callback()
def _root(seed: int | None = typer.Option(None, "--seed", help="Seed the RNG (testing).")):
    if seed is not None:
        rng.seed(seed)


def emit(payload: dict) -> None:
    typer.echo(json.dumps(payload))


def fail(code: str, message: str) -> None:
    typer.echo(json.dumps({"error": {"code": code, "message": message}}))
    raise typer.Exit(1)


def guard(fn, *args, **kwargs):
    """Run fn, converting EngineError/ValueError into JSON failures."""
    try:
        return fn(*args, **kwargs)
    except EngineError as e:
        fail(e.code, e.message)
    except ValueError as e:
        fail("bad_expr", str(e))


def d20_roll(modifier: int, adv: bool, dis: bool) -> tuple[int, int]:
    """Return (natural, total) for a d20, honoring advantage/disadvantage."""
    a = rng.randint(1, 20)
    if adv == dis:
        nat = a
    else:
        b = rng.randint(1, 20)
        nat = max(a, b) if adv else min(a, b)
    return nat, nat + modifier


@app.command()
def roll(
    expr: str,
    vs: int | None = typer.Option(None, help="Difficulty to beat (total >= vs)."),
    adv: bool = typer.Option(False, "--adv"),
    dis: bool = typer.Option(False, "--dis"),
):
    count, sides, modifier = guard(dice.parse, expr)
    if (adv or dis) and (count, sides) != (1, 20):
        fail("bad_expr", "--adv/--dis only apply to a single d20")
    if adv or dis:
        nat, total = d20_roll(modifier, adv, dis)
        rolls = [nat]
    else:
        result = dice.roll(expr, rng)
        rolls, total = result.rolls, result.total
    crit = None
    if (count, sides) == (1, 20):
        crit = "hit" if rolls[0] == 20 else "fumble" if rolls[0] == 1 else None
    payload = {"expr": expr, "rolls": rolls, "modifier": modifier, "total": total, "crit": crit}
    if vs is not None:
        payload.update(vs=vs, success=total >= vs)
    emit(payload)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd engine && uv run pytest -q`
Expected: all PASS. Also smoke: `uv run engine roll 2d6+3` prints a JSON object.

- [ ] **Step 6: Commit**

```bash
git add engine .gitignore
git commit -m "feat(engine): scaffold uv/Typer CLI with dice roller"
```

---

### Task 2: Game definition loading + validation (`engine game validate`) + test fixture game

**Files:**
- Create: `engine/src/ttrpg_engine/game.py`, `engine/tests/fixtures/minigame/**` (below), `engine/tests/conftest.py` (fixture-path constant only for now)
- Modify: `engine/src/ttrpg_engine/cli.py`
- Test: `engine/tests/test_game.py`

**Interfaces:**
- Consumes: `cli.emit/fail/guard`, `errors.EngineError`.
- Produces: `game.load(path: Path) -> dict` with keys `meta, core, attributes, classes, races, spells, effects, combat, recovery, progression, economy, items, content_dir`; `game.validate(path: Path) -> list[str]` (error strings, empty = valid). Command `engine game validate PATH`. Fixture game at `engine/tests/fixtures/minigame/` used by all later tests; `tests/conftest.py` exports `FIXTURE_GAME`.

- [ ] **Step 1: Create the fixture minigame**

A complete, tiny game. Directory `engine/tests/fixtures/minigame/`:

`game.yaml`:

```yaml
name: minigame
version: 0.1.0
description: Fixture game for engine tests.
start_date: "1203-04-17"
start_hour: 9
start_location: town
```

`ruleset/core.yaml`:

```yaml
resolution: d20_vs_dc
crit_on: 20
fumble_on: 1
standard_array: [15, 14, 13, 12, 10, 8]
dcs: {easy: 10, medium: 13, hard: 16}
```

`ruleset/attributes.yaml`:

```yaml
order: [STR, DEX, CON, INT, WIS, CHA]
```

`ruleset/classes/fighter.yaml`:

```yaml
name: fighter
hit_die: 10
cast_attr: null
skill_choices: 2
skills: [athletics, intimidation, perception, survival]
starting_gear: [chain_mail, longsword]
starting_gold: 10
levels:
  1: {features: [second_wind], spells: [], slots: {}}
  2: {features: [], spells: [], slots: {}}
  3: {features: [improved_critical], spells: [], slots: {}}
```

`ruleset/classes/cleric.yaml`:

```yaml
name: cleric
hit_die: 8
cast_attr: WIS
skill_choices: 2
skills: [insight, medicine, persuasion, religion]
starting_gear: [leather_armor, mace]
starting_gold: 15
levels:
  1: {features: [], spells: [sacred_flame, cure_wounds], slots: {1: 2}}
  2: {features: [], spells: [bless], slots: {1: 3}}
  3: {features: [], spells: [], slots: {1: 4}}
```

`ruleset/races.yaml`:

```yaml
human: {bonuses: {CON: 1, WIS: 1}, speed: 6}
dwarf: {bonuses: {CON: 2}, speed: 5}
```

`ruleset/spells.yaml`:

```yaml
sacred_flame:
  level: 0
  action: action
  range: 12
  resolve: save
  save_attr: DEX
  damage: 1d8
  on_save: none
cure_wounds:
  level: 1
  action: action
  range: 1
  resolve: auto
  heal: 1d8+CASTMOD
bless:
  level: 1
  action: action
  range: 6
  resolve: auto
  effect: {name: blessed, duration: 10}
```

`ruleset/effects.yaml`:

```yaml
blessed: {impact: "+1d4 hint to GM on attacks and saves (adjudicated via --adv where fitting)"}
poisoned: {impact: "GM applies --dis on attacks and checks"}
unconscious: {impact: "cannot act; attacks against have --adv"}
dying: {impact: "must make death saves; see recovery"}
```

`ruleset/combat.yaml`:

```yaml
initiative: {die: d20, attr: DEX}
turn: {move: speed, actions: 1}
diagonal_cost: 1
```

`ruleset/recovery.yaml`:

```yaml
short_rest: {hours: 1}
long_rest: {hours: 8}
death_save: {dc: 10, fails_to_die: 3, successes_to_stable: 3}
```

`ruleset/progression.yaml`:

```yaml
proficiency: {1: 2, 2: 2, 3: 2}
xp_thresholds: {2: 300, 3: 900}
max_level: 3
```

`ruleset/economy.yaml`:

```yaml
currency: gp
```

`ruleset/items.yaml`:

```yaml
longsword: {type: weapon, damage: 1d8, finesse: false, range: 1, price: 15}
mace: {type: weapon, damage: 1d6, finesse: false, range: 1, price: 5}
dagger: {type: weapon, damage: 1d4, finesse: true, range: 1, price: 2}
chain_mail: {type: armor, ac_base: 16, add_dex: false, price: 75}
leather_armor: {type: armor, ac_base: 11, add_dex: true, price: 10}
torch: {type: gear, price: 1}
```

`content/maps/region.yaml`:

```yaml
nodes:
  town: {name: Town, coords: [0, 0], terrain: settlement}
  cave: {name: Cave, coords: [8, 3], terrain: hills}
edges:
  - {between: [town, cave], hours: 4}
```

`content/maps/encounters/skirmish.yaml`:

```yaml
id: skirmish
name: Skirmish
grid: {width: 12, height: 8}
terrain:
  - {type: wall, cells: [[4, 0], [4, 1], [4, 2]]}
  - {type: difficult, cells: [[7, 5], [8, 5]]}
monsters:
  - {type: goblin, pos: [9, 4]}
  - {type: goblin, pos: [10, 4]}
pc_spawns: [[1, 3], [2, 3], [1, 4], [2, 4]]
```

`content/bestiary/goblin.yaml`:

```yaml
name: Goblin
ac: 13
hp: 7
speed: 6
attributes: {STR: 8, DEX: 14, CON: 10, INT: 10, WIS: 8, CHA: 8}
attacks: [{name: scimitar, attack_mod: 4, damage: 1d6+2, range: 1}]
xp: 50
loot: {gold: 1d6, items: []}
difficulty: easy
```

`content/npcs.yaml`:

```yaml
mayor: {name: The Mayor, location: town, role: quest-giver, disposition: friendly}
```

`content/factions.yaml`:

```yaml
town_watch: {name: Town Watch, goals: [keep order], relations: {}}
```

`content/history.md`:

```markdown
# History

A small town near a goblin-infested cave. That is all.
```

`engine/tests/conftest.py`:

```python
from pathlib import Path

FIXTURE_GAME = Path(__file__).parent / "fixtures" / "minigame"
```

- [ ] **Step 2: Write the failing tests**

`engine/tests/test_game.py`:

```python
import json
import shutil

from typer.testing import CliRunner

from ttrpg_engine import game
from ttrpg_engine.cli import app
from .conftest import FIXTURE_GAME

runner = CliRunner()


def test_load_keys():
    g = game.load(FIXTURE_GAME)
    assert g["meta"]["name"] == "minigame"
    assert g["classes"]["fighter"]["hit_die"] == 10
    assert g["items"]["dagger"]["finesse"] is True
    assert g["content_dir"] == FIXTURE_GAME / "content"


def test_validate_ok():
    assert game.validate(FIXTURE_GAME) == []


def test_validate_catches_bad_edge_and_missing_class_file(tmp_path):
    broken = tmp_path / "broken"
    shutil.copytree(FIXTURE_GAME, broken)
    (broken / "ruleset" / "classes" / "fighter.yaml").unlink()
    region = broken / "content" / "maps" / "region.yaml"
    region.write_text(region.read_text().replace("cave]", "nowhere]"))
    errors = game.validate(broken)
    assert any("nowhere" in e for e in errors)


def test_cli_validate():
    res = runner.invoke(app, ["game", "validate", str(FIXTURE_GAME)])
    assert res.exit_code == 0
    assert json.loads(res.stdout) == {"valid": True, "game": "minigame", "errors": []}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd engine && uv run pytest tests/test_game.py -q`
Expected: FAIL — no module `ttrpg_engine.game`.

- [ ] **Step 4: Implement**

`engine/src/ttrpg_engine/game.py`:

```python
from pathlib import Path

import yaml

from ttrpg_engine.errors import EngineError

_RULESET_FILES = ["core", "attributes", "races", "spells", "effects",
                  "combat", "recovery", "progression", "economy", "items"]
ATTRS = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]


def _read(path: Path):
    if not path.exists():
        raise EngineError("game_invalid", f"missing file: {path}")
    return yaml.safe_load(path.read_text()) or {}


def load(path: Path) -> dict:
    path = Path(path)
    g = {"meta": _read(path / "game.yaml"), "content_dir": path / "content"}
    for name in _RULESET_FILES:
        g[name] = _read(path / "ruleset" / f"{name}.yaml")
    g["classes"] = {}
    classes_dir = path / "ruleset" / "classes"
    if not classes_dir.is_dir():
        raise EngineError("game_invalid", f"missing dir: {classes_dir}")
    for f in sorted(classes_dir.glob("*.yaml")):
        g["classes"][f.stem] = _read(f)
    return g


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        g = load(path)
    except EngineError as e:
        return [e.message]
    max_level = g["progression"].get("max_level", 1)
    for cname, cls in g["classes"].items():
        for lvl in range(1, max_level + 1):
            if lvl not in cls.get("levels", {}):
                errors.append(f"class {cname}: missing level {lvl} row")
        for item in cls.get("starting_gear", []):
            if item not in g["items"]:
                errors.append(f"class {cname}: unknown starting item {item}")
        for row in cls.get("levels", {}).values():
            for spell in row.get("spells", []):
                if spell not in g["spells"]:
                    errors.append(f"class {cname}: unknown spell {spell}")
    for mname, mon in _bestiary(g).items():
        for field in ["name", "ac", "hp", "speed", "attributes", "attacks", "xp"]:
            if field not in mon:
                errors.append(f"monster {mname}: missing {field}")
    region = g["content_dir"] / "maps" / "region.yaml"
    if region.exists():
        rmap = yaml.safe_load(region.read_text()) or {}
        nodes = set(rmap.get("nodes", {}))
        for edge in rmap.get("edges", []):
            for end in edge.get("between", []):
                if end not in nodes:
                    errors.append(f"region edge references unknown node {end}")
    else:
        errors.append("missing content/maps/region.yaml")
    return errors


def _bestiary(g: dict) -> dict:
    out = {}
    bdir = g["content_dir"] / "bestiary"
    if bdir.is_dir():
        for f in sorted(bdir.glob("*.yaml")):
            out[f.stem] = yaml.safe_load(f.read_text()) or {}
    return out


def bestiary_entry(g: dict, monster_type: str) -> dict:
    entry = _bestiary(g).get(monster_type)
    if entry is None:
        raise EngineError("unknown_monster", f"no bestiary entry: {monster_type}")
    return entry
```

Add to `engine/src/ttrpg_engine/cli.py` (after the `roll` command):

```python
from pathlib import Path

from ttrpg_engine import game as game_mod

game_app = typer.Typer()
app.add_typer(game_app, name="game")


@game_app.command("validate")
def game_validate(path: Path):
    errors = game_mod.validate(path)
    if errors:
        emit({"valid": False, "errors": errors})
        raise typer.Exit(1)
    meta = game_mod.load(path)["meta"]
    emit({"valid": True, "game": meta["name"], "errors": []})
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd engine && uv run pytest -q`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add engine
git commit -m "feat(engine): game definition loader, validator, and fixture minigame"
```

---

### Task 3: World discovery, `engine world init`, `engine state get`

**Files:**
- Create: `engine/src/ttrpg_engine/worldfs.py`
- Modify: `engine/src/ttrpg_engine/cli.py`, `engine/tests/conftest.py`
- Test: `engine/tests/test_world.py`

**Interfaces:**
- Consumes: `game.load`, `game.validate`, `cli` helpers.
- Produces: `worldfs.find_root(start: Path | None = None) -> Path` (raises `EngineError("no_world", ...)`); `worldfs.read_yaml(path: Path) -> dict`; `worldfs.write_yaml(path: Path, data) -> None` (atomic, creates parents); `worldfs.init_world(dest: Path, game_path: Path, name: str) -> None`; `worldfs.state(root: Path, rel: str) -> Path` (maps `"party/pc-brin"` → `root/"state/party/pc-brin.yaml"`); `worldfs.load_game_for(root: Path) -> dict` (reads `world.yaml` game path, returns `game.load` result). Commands `engine world init DEST --game PATH --name NAME`, `engine state get REL [--key dotted.path]`. Pytest fixture `wroot` (a ready world, cwd-chdir'd).

- [ ] **Step 1: Write the failing tests**

`engine/tests/test_world.py`:

```python
import json

from typer.testing import CliRunner

from ttrpg_engine import worldfs
from ttrpg_engine.cli import app
from ttrpg_engine.errors import EngineError
from .conftest import FIXTURE_GAME

runner = CliRunner()


def test_init_world_layout(tmp_path):
    root = tmp_path / "w"
    worldfs.init_world(root, FIXTURE_GAME, "Testia")
    manifest = worldfs.read_yaml(root / "world.yaml")
    assert manifest["world"] == "Testia"
    assert manifest["game"]["name"] == "minigame"
    clock = worldfs.read_yaml(root / "state" / "clock.yaml")
    assert (str(clock["date"]), clock["hour"]) == ("1203-04-17", 9)
    party = worldfs.read_yaml(root / "state" / "party.yaml")
    assert party == {"members": [], "location": "town", "gold": 0, "stash": []}
    assert (root / "canon" / "maps" / "region.yaml").exists()
    assert (root / "timeline").is_dir() and (root / "sessions").is_dir()
    assert "renders/" in (root / ".gitignore").read_text()


def test_find_root_walks_up(tmp_path, monkeypatch):
    root = tmp_path / "w"
    worldfs.init_world(root, FIXTURE_GAME, "Testia")
    deep = root / "canon" / "maps"
    monkeypatch.chdir(deep)
    assert worldfs.find_root() == root
    monkeypatch.chdir(tmp_path)
    try:
        worldfs.find_root()
        raise AssertionError("should have raised")
    except EngineError as e:
        assert e.code == "no_world"


def test_state_get(wroot):
    res = runner.invoke(app, ["state", "get", "clock", "--key", "hour"])
    assert res.exit_code == 0
    assert json.loads(res.stdout) == {"path": "clock", "key": "hour", "value": 9}
```

Replace `engine/tests/conftest.py` with:

```python
from pathlib import Path

import pytest

from ttrpg_engine import worldfs

FIXTURE_GAME = Path(__file__).parent / "fixtures" / "minigame"


@pytest.fixture
def wroot(tmp_path, monkeypatch):
    root = tmp_path / "testworld"
    worldfs.init_world(root, FIXTURE_GAME, "Test World")
    monkeypatch.chdir(root)
    return root
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd engine && uv run pytest tests/test_world.py -q`
Expected: FAIL — no module `ttrpg_engine.worldfs`.

- [ ] **Step 3: Implement**

`engine/src/ttrpg_engine/worldfs.py`:

```python
import datetime
import os
import shutil
import tempfile
from pathlib import Path

import yaml

from ttrpg_engine import game as game_mod
from ttrpg_engine.errors import EngineError


def find_root(start: Path | None = None) -> Path:
    cur = (start or Path.cwd()).resolve()
    for p in [cur, *cur.parents]:
        if (p / "world.yaml").exists():
            return p
    raise EngineError("no_world", "no world.yaml found from cwd upward (use --world or cd into a world repo)")


def read_yaml(path: Path) -> dict:
    if not path.exists():
        raise EngineError("not_found", f"missing state file: {path}")
    return yaml.safe_load(path.read_text()) or {}


def write_yaml(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
    os.replace(tmp, path)


def state(root: Path, rel: str) -> Path:
    return root / "state" / f"{rel}.yaml"


def load_game_for(root: Path) -> dict:
    manifest = read_yaml(root / "world.yaml")
    return game_mod.load(Path(manifest["game"]["path"]))


def init_world(dest: Path, game_path: Path, name: str) -> None:
    dest = Path(dest)
    if (dest / "world.yaml").exists():
        raise EngineError("exists", f"{dest} is already a world")
    errors = game_mod.validate(game_path)
    if errors:
        raise EngineError("game_invalid", "; ".join(errors))
    g = game_mod.load(game_path)
    dest.mkdir(parents=True, exist_ok=True)
    write_yaml(dest / "world.yaml", {
        "world": name,
        "game": {"name": g["meta"]["name"], "version": str(g["meta"]["version"]),
                 "path": str(Path(game_path).resolve())},
        "created": datetime.date.today().isoformat(),
    })
    shutil.copytree(g["content_dir"], dest / "canon")
    write_yaml(state(dest, "clock"), {"date": str(g["meta"]["start_date"]),
                                      "hour": g["meta"]["start_hour"]})
    write_yaml(state(dest, "party"), {"members": [], "location": g["meta"]["start_location"],
                                      "gold": 0, "stash": []})
    write_yaml(state(dest, "session"), {"current": 0})
    (dest / "timeline").mkdir()
    (dest / "sessions").mkdir()
    (dest / "renders").mkdir()
    (dest / ".gitignore").write_text("renders/\n")
```

Add to `engine/src/ttrpg_engine/cli.py`:

```python
from ttrpg_engine import worldfs

world_app = typer.Typer()
state_app = typer.Typer()
app.add_typer(world_app, name="world")
app.add_typer(state_app, name="state")

_world_override: Path | None = None


def require_root() -> Path:
    return guard(worldfs.find_root, _world_override)


@world_app.command("init")
def world_init(dest: Path, game: Path = typer.Option(...), name: str = typer.Option(...)):
    guard(worldfs.init_world, dest, game, name)
    emit({"world": name, "path": str(Path(dest).resolve())})


@state_app.command("get")
def state_get(path: str, key: str | None = typer.Option(None)):
    root = require_root()
    data = guard(worldfs.read_yaml, worldfs.state(root, path))
    value = data
    if key:
        for part in key.split("."):
            if not isinstance(value, dict) or part not in value:
                fail("not_found", f"key {key!r} not in state/{path}.yaml")
            value = value[part]
    emit({"path": path, "key": key, "value": value})
```

And extend the root callback to accept `--world` (replace the existing `_root`):

```python
@app.callback()
def _root(
    seed: int | None = typer.Option(None, "--seed", help="Seed the RNG (testing)."),
    world: Path | None = typer.Option(None, "--world", help="World repo path (default: discover from cwd)."),
):
    global _world_override
    if seed is not None:
        rng.seed(seed)
    _world_override = world
```

(Note: `find_root(None)` must keep working — `_world_override` is `None` unless `--world` given.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd engine && uv run pytest -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add engine
git commit -m "feat(engine): world init, cwd world discovery, state get"
```

---

### Task 4: Timeline events, `engine session start`, `engine override log`

**Files:**
- Create: `engine/src/ttrpg_engine/timeline.py`, `engine/src/ttrpg_engine/clock.py`
- Modify: `engine/src/ttrpg_engine/cli.py`
- Test: `engine/tests/test_timeline.py`

**Interfaces:**
- Consumes: `worldfs.read_yaml/write_yaml/state`, `cli` helpers.
- Produces: `clock.advance(clock: dict, hours: int) -> dict` (12×30 calendar, returns new `{date, hour}`); `timeline.append_event(root: Path, *, type_: str, summary: str, actors: list[str] | None = None, delta: dict | None = None, override: bool = False) -> str` (returns event id `YYYY-MM-DD-NNN`; reads clock + session for stamps); `timeline.events_for_date(root, date) -> list[Path]`. Commands `engine session start` (increments `state/session.yaml`, mkdirs `sessions/session-NNN/`, appends `session` event), `engine override log --summary TEXT [--actors a,b]` (appends event with `override: true`). **Every later mutating task calls `timeline.append_event` — this is the audit-log backbone.**

- [ ] **Step 1: Write the failing tests**

`engine/tests/test_timeline.py`:

```python
import json

from typer.testing import CliRunner

from ttrpg_engine import clock, timeline, worldfs
from ttrpg_engine.cli import app

runner = CliRunner()


def test_clock_advance_rolls_days_and_months():
    c = {"date": "1203-04-29", "hour": 20}
    c2 = clock.advance(c, 10)
    assert c2 == {"date": "1203-04-30", "hour": 6}
    c3 = clock.advance(c2, 24 * 1)
    assert c3["date"] == "1203-05-01"


def test_append_event_ids_increment(wroot):
    e1 = timeline.append_event(wroot, type_="gold", summary="found 5gp")
    e2 = timeline.append_event(wroot, type_="gold", summary="found 2gp")
    assert e1 == "1203-04-17-001"
    assert e2 == "1203-04-17-002"
    data = worldfs.read_yaml(wroot / "timeline" / f"{e2}.yaml")
    assert data["type"] == "gold" and data["session"] == 0 and data["override"] is False


def test_session_start_and_override_log(wroot):
    res = runner.invoke(app, ["session", "start"])
    assert json.loads(res.stdout) == {"session": 1}
    assert (wroot / "sessions" / "session-001").is_dir()
    res = runner.invoke(app, ["override", "log", "--summary", "GM fiat: gate is open"])
    ev = json.loads(res.stdout)["event"]
    data = worldfs.read_yaml(wroot / "timeline" / f"{ev}.yaml")
    assert data["override"] is True and data["session"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd engine && uv run pytest tests/test_timeline.py -q`
Expected: FAIL — missing modules.

- [ ] **Step 3: Implement**

`engine/src/ttrpg_engine/clock.py`:

```python
def advance(clock: dict, hours: int) -> dict:
    h = clock["hour"] + hours
    days, h = divmod(h, 24)
    y, m, d = (int(x) for x in str(clock["date"]).split("-"))
    d += days
    while d > 30:
        d -= 30
        m += 1
    while m > 12:
        m -= 12
        y += 1
    return {"date": f"{y:04d}-{m:02d}-{d:02d}", "hour": h}
```

`engine/src/ttrpg_engine/timeline.py`:

```python
from pathlib import Path

from ttrpg_engine import worldfs


def events_for_date(root: Path, date: str) -> list[Path]:
    return sorted((root / "timeline").glob(f"{date}-*.yaml"))


def append_event(root: Path, *, type_: str, summary: str,
                 actors: list[str] | None = None, delta: dict | None = None,
                 override: bool = False) -> str:
    clk = worldfs.read_yaml(worldfs.state(root, "clock"))
    session = worldfs.read_yaml(worldfs.state(root, "session"))["current"]
    date = str(clk["date"])
    seq = len(events_for_date(root, date)) + 1
    event_id = f"{date}-{seq:03d}"
    worldfs.write_yaml(root / "timeline" / f"{event_id}.yaml", {
        "id": event_id, "session": session, "type": type_,
        "date": date, "hour": clk["hour"],
        "actors": actors or [], "summary": summary,
        "delta": delta or {}, "override": override,
    })
    return event_id
```

Add to `engine/src/ttrpg_engine/cli.py`:

```python
from ttrpg_engine import timeline

session_app = typer.Typer()
override_app = typer.Typer()
app.add_typer(session_app, name="session")
app.add_typer(override_app, name="override")


@session_app.command("start")
def session_start():
    root = require_root()
    sess = worldfs.read_yaml(worldfs.state(root, "session"))
    sess["current"] += 1
    worldfs.write_yaml(worldfs.state(root, "session"), sess)
    (root / "sessions" / f"session-{sess['current']:03d}").mkdir(parents=True, exist_ok=True)
    timeline.append_event(root, type_="session", summary=f"session {sess['current']} started")
    emit({"session": sess["current"]})


@override_app.command("log")
def override_log(summary: str = typer.Option(...), actors: str = typer.Option("", help="comma-separated ids")):
    root = require_root()
    actor_list = [a for a in actors.split(",") if a]
    event = timeline.append_event(root, type_="override", summary=summary,
                                  actors=actor_list, override=True)
    emit({"event": event})
```

(Note: `session start` appends a `session` event — add `session` to the allowed `type` list in the schema comment at the top of this plan; it is already implied.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd engine && uv run pytest -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add engine
git commit -m "feat(engine): timeline events, session start, override log"
```

---

### Task 5: Character creation (`engine char create`) + sheets

**Files:**
- Create: `engine/src/ttrpg_engine/chargen.py`
- Modify: `engine/src/ttrpg_engine/cli.py`, `engine/tests/conftest.py`
- Test: `engine/tests/test_chargen.py`

**Interfaces:**
- Consumes: `worldfs`, `timeline.append_event`, `game` dict shape, `dice.roll`.
- Produces: `chargen.attr_mod(score: int) -> int`; `chargen.create(root: Path, g: dict, *, name: str, cls_name: str, race_name: str, assign: dict[str, int], skills: list[str]) -> dict` (returns the sheet, writes `state/party/pc-<slug>.yaml`, appends to `party.members`, appends `character` event); sheet schema as defined in File Structure. Command `engine char create --name Brin --class rogue --race human --assign DEX=15,WIS=14,INT=13,CON=12,STR=10,CHA=8 --skills stealth,perception,deception`. Conftest gains `make_pc(wroot, name="Brin", cls="fighter", ...)` helper used by combat tests.

- [ ] **Step 1: Write the failing tests**

`engine/tests/test_chargen.py`:

```python
import json

from typer.testing import CliRunner

from ttrpg_engine import chargen, worldfs
from ttrpg_engine.cli import app
from ttrpg_engine.errors import EngineError

runner = CliRunner()

ASSIGN = "STR=15,CON=14,DEX=13,WIS=12,INT=10,CHA=8"


def test_attr_mod():
    assert chargen.attr_mod(15) == 2
    assert chargen.attr_mod(10) == 0
    assert chargen.attr_mod(8) == -1


def test_cli_create_fighter(wroot):
    res = runner.invoke(app, ["char", "create", "--name", "Borin", "--class", "fighter",
                              "--race", "dwarf", "--assign", ASSIGN,
                              "--skills", "athletics,perception"])
    assert res.exit_code == 0, res.stdout
    sheet = worldfs.read_yaml(wroot / "state" / "party" / "pc-borin.yaml")
    assert sheet["attributes"]["CON"] == 16          # 14 + dwarf +2
    assert sheet["max_hp"] == 13                     # d10 max + CON mod 3
    assert sheet["ac"] == 16                         # chain mail, no dex
    atk = sheet["attacks"][0]
    assert atk == {"name": "longsword", "attack_mod": 4, "damage": "1d8+2", "range": 1}
    party = worldfs.read_yaml(wroot / "state" / "party.yaml")
    assert party["members"] == ["pc-borin"]
    assert len(list((wroot / "timeline").glob("*.yaml"))) == 1


def test_create_rejects_bad_array(wroot):
    from .conftest import FIXTURE_GAME
    from ttrpg_engine import game
    g = game.load(FIXTURE_GAME)
    try:
        chargen.create(wroot, g, name="X", cls_name="fighter", race_name="human",
                       assign={"STR": 18, "DEX": 14, "CON": 13, "INT": 12, "WIS": 10, "CHA": 8},
                       skills=["athletics", "perception"])
        raise AssertionError("should have raised")
    except EngineError as e:
        assert e.code == "bad_assign"


def test_cleric_gets_spells_and_slots(wroot):
    res = runner.invoke(app, ["char", "create", "--name", "Mira", "--class", "cleric",
                              "--race", "human", "--assign",
                              "WIS=15,CON=14,STR=13,DEX=12,INT=10,CHA=8",
                              "--skills", "insight,medicine"])
    assert res.exit_code == 0, res.stdout
    # read from disk, not the CLI JSON: JSON stringifies the int slot-level keys
    sheet = worldfs.read_yaml(wroot / "state" / "party" / "pc-mira.yaml")
    assert sheet["spells_known"] == ["sacred_flame", "cure_wounds"]
    assert sheet["spell_slots"] == {1: {"max": 2, "current": 2}}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd engine && uv run pytest tests/test_chargen.py -q`
Expected: FAIL — no module `ttrpg_engine.chargen`.

- [ ] **Step 3: Implement**

`engine/src/ttrpg_engine/chargen.py`:

```python
import re
from pathlib import Path

from ttrpg_engine import timeline, worldfs
from ttrpg_engine.errors import EngineError
from ttrpg_engine.game import ATTRS


def attr_mod(score: int) -> int:
    return (score - 10) // 2


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _armor_class(g: dict, gear: list[str], dex: int) -> int:
    for item in gear:
        spec = g["items"][item]
        if spec["type"] == "armor":
            return spec["ac_base"] + (attr_mod(dex) if spec["add_dex"] else 0)
    return 10 + attr_mod(dex)


def _attacks(g: dict, gear: list[str], attrs: dict, prof: int) -> list[dict]:
    out = []
    for item in gear:
        spec = g["items"][item]
        if spec["type"] != "weapon":
            continue
        use_dex = spec["finesse"] and attrs["DEX"] >= attrs["STR"]
        mod = attr_mod(attrs["DEX" if use_dex else "STR"])
        dmg = spec["damage"] + (f"{mod:+d}" if mod else "")
        out.append({"name": item, "attack_mod": mod + prof,
                    "damage": dmg, "range": spec["range"]})
    return out


def create(root: Path, g: dict, *, name: str, cls_name: str, race_name: str,
           assign: dict[str, int], skills: list[str]) -> dict:
    if cls_name not in g["classes"]:
        raise EngineError("unknown_class", f"no class {cls_name}")
    if race_name not in g["races"]:
        raise EngineError("unknown_race", f"no race {race_name}")
    cls, race = g["classes"][cls_name], g["races"][race_name]
    if sorted(assign) != sorted(ATTRS):
        raise EngineError("bad_assign", f"assign must cover exactly {ATTRS}")
    if sorted(assign.values()) != sorted(g["core"]["standard_array"]):
        raise EngineError("bad_assign", f"values must be the standard array {g['core']['standard_array']}")
    if len(skills) != cls["skill_choices"] or not set(skills) <= set(cls["skills"]):
        raise EngineError("bad_skills", f"pick exactly {cls['skill_choices']} of {cls['skills']}")
    attrs = {a: assign[a] + race.get("bonuses", {}).get(a, 0) for a in ATTRS}
    prof = g["progression"]["proficiency"][1]
    level1 = cls["levels"][1]
    pc_id = f"pc-{_slug(name)}"
    if worldfs.state(root, f"party/{pc_id}").exists():
        raise EngineError("exists", f"{pc_id} already exists")
    max_hp = max(1, cls["hit_die"] + attr_mod(attrs["CON"]))
    sheet = {
        "id": pc_id, "name": name, "class": cls_name, "race": race_name,
        "level": 1, "xp": 0, "attributes": attrs,
        "max_hp": max_hp, "hp": max_hp,
        "ac": _armor_class(g, cls["starting_gear"], attrs["DEX"]),
        "speed": race["speed"], "proficiency": prof, "skills": skills,
        "attacks": _attacks(g, cls["starting_gear"], attrs, prof),
        "spells_known": list(level1["spells"]),
        "spell_slots": {lvl: {"max": n, "current": n} for lvl, n in level1["slots"].items()},
        "features": list(level1["features"]),
        "inventory": [{"item": i, "qty": 1} for i in cls["starting_gear"]],
        "gold": cls["starting_gold"], "effects": [],
    }
    worldfs.write_yaml(worldfs.state(root, f"party/{pc_id}"), sheet)
    party = worldfs.read_yaml(worldfs.state(root, "party"))
    party["members"].append(pc_id)
    worldfs.write_yaml(worldfs.state(root, "party"), party)
    timeline.append_event(root, type_="character", actors=[pc_id],
                          summary=f"{name} the {race_name} {cls_name} joins the party")
    return sheet
```

Add to `engine/src/ttrpg_engine/cli.py`:

```python
from ttrpg_engine import chargen

char_app = typer.Typer()
app.add_typer(char_app, name="char")


def parse_kv_ints(spec: str) -> dict[str, int]:
    out = {}
    for pair in spec.split(","):
        k, _, v = pair.partition("=")
        if not v.lstrip("-").isdigit():
            fail("bad_assign", f"bad assignment {pair!r}")
        out[k.strip().upper()] = int(v)
    return out


@char_app.command("create")
def char_create(
    name: str = typer.Option(...),
    cls: str = typer.Option(..., "--class"),
    race: str = typer.Option(...),
    assign: str = typer.Option(..., help="e.g. DEX=15,WIS=14,INT=13,CON=12,STR=10,CHA=8"),
    skills: str = typer.Option(..., help="comma-separated"),
):
    root = require_root()
    g = guard(worldfs.load_game_for, root)
    sheet = guard(chargen.create, root, g, name=name, cls_name=cls, race_name=race,
                  assign=parse_kv_ints(assign), skills=[s.strip() for s in skills.split(",")])
    emit({"sheet": sheet})
```

Add to `engine/tests/conftest.py`:

```python
from typer.testing import CliRunner

_runner = CliRunner()


def make_pc(name="Borin", cls="fighter", race="dwarf",
            assign="STR=15,CON=14,DEX=13,WIS=12,INT=10,CHA=8",
            skills="athletics,perception"):
    from ttrpg_engine.cli import app
    res = _runner.invoke(app, ["char", "create", "--name", name, "--class", cls,
                               "--race", race, "--assign", assign, "--skills", skills])
    assert res.exit_code == 0, res.stdout
    return f"pc-{name.lower()}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd engine && uv run pytest -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add engine
git commit -m "feat(engine): character creation with derived stats"
```

---

### Task 6: Skill/attribute checks (`engine check`)

**Files:**
- Create: `engine/src/ttrpg_engine/checks.py`
- Modify: `engine/src/ttrpg_engine/cli.py`
- Test: `engine/tests/test_checks.py`

**Interfaces:**
- Consumes: sheets from Task 5, `cli.d20_roll`, `chargen.attr_mod`.
- Produces: `checks.run(root: Path, actor: str, attr: str, dc: int, *, skill: str | None, adv: bool, dis: bool, roll_fn) -> dict` where `roll_fn(modifier, adv, dis) -> (natural, total)` (pass `cli.d20_roll`). Returns `{actor, attr, skill, modifier, natural, total, dc, success, crit}`. Command `engine check --actor pc-borin --attr WIS --dc 12 [--skill perception] [--adv|--dis]`. Read-only: no timeline event.

- [ ] **Step 1: Write the failing test**

`engine/tests/test_checks.py`:

```python
import json

from typer.testing import CliRunner

from ttrpg_engine.cli import app
from .conftest import make_pc

runner = CliRunner()


def test_check_applies_proficiency(wroot):
    pc = make_pc()  # dwarf fighter, WIS 12 (+1), proficient in perception (prof +2)
    res = runner.invoke(app, ["--seed", "3", "check", "--actor", pc,
                              "--attr", "WIS", "--skill", "perception", "--dc", "12"])
    assert res.exit_code == 0, res.stdout
    data = json.loads(res.stdout)
    assert data["modifier"] == 3
    assert data["total"] == data["natural"] + 3
    assert data["success"] == (data["total"] >= 12)


def test_check_unknown_actor_fails(wroot):
    res = runner.invoke(app, ["check", "--actor", "pc-nobody", "--attr", "STR", "--dc", "10"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "not_found"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd engine && uv run pytest tests/test_checks.py -q`
Expected: FAIL — no module `ttrpg_engine.checks`.

- [ ] **Step 3: Implement**

`engine/src/ttrpg_engine/checks.py`:

```python
from pathlib import Path

from ttrpg_engine import worldfs
from ttrpg_engine.chargen import attr_mod


def run(root: Path, actor: str, attr: str, dc: int, *,
        skill: str | None, adv: bool, dis: bool, roll_fn) -> dict:
    sheet = worldfs.read_yaml(worldfs.state(root, f"party/{actor}"))
    modifier = attr_mod(sheet["attributes"][attr])
    if skill and skill in sheet["skills"]:
        modifier += sheet["proficiency"]
    natural, total = roll_fn(modifier, adv, dis)
    crit = "hit" if natural == 20 else "fumble" if natural == 1 else None
    return {"actor": actor, "attr": attr, "skill": skill, "modifier": modifier,
            "natural": natural, "total": total, "dc": dc,
            "success": total >= dc, "crit": crit}
```

Add to `engine/src/ttrpg_engine/cli.py`:

```python
from ttrpg_engine import checks


@app.command()
def check(
    actor: str = typer.Option(...),
    attr: str = typer.Option(...),
    dc: int = typer.Option(...),
    skill: str | None = typer.Option(None),
    adv: bool = typer.Option(False, "--adv"),
    dis: bool = typer.Option(False, "--dis"),
):
    root = require_root()
    emit(guard(checks.run, root, actor, attr.upper(), dc,
               skill=skill, adv=adv, dis=dis, roll_fn=d20_roll))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd engine && uv run pytest -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add engine
git commit -m "feat(engine): d20 checks vs DC with skill proficiency"
```

---

### Task 7: Grid math + ASCII map render (`engine map render`)

**Files:**
- Create: `engine/src/ttrpg_engine/grid.py`, `engine/src/ttrpg_engine/render.py`
- Modify: `engine/src/ttrpg_engine/cli.py`
- Test: `engine/tests/test_grid_render.py`

**Interfaces:**
- Consumes: encounter schema (File Structure section); no encounter *lifecycle* yet — tests build the dict by hand and write it to `state/encounter.yaml`.
- Produces: `grid.chebyshev(a: tuple[int,int], b: tuple[int,int]) -> int`; `grid.cells_of(enc: dict, terrain_type: str) -> set[tuple[int,int]]`; `grid.blocked(enc: dict, cell: tuple[int,int]) -> str | None` (returns `"oob"`, `"wall"`, `"occupied"`, or `None`); `render.ascii_map(enc: dict) -> str` (deterministic; PCs get uppercase initials, monsters lowercase, collisions walk the alphabet, `#` wall, `~` difficult, `.` empty; column header + legend lines); `render.symbols(enc: dict) -> dict[str, str]`. Command `engine map render` → `{"map": "<ascii>", "round": N, "turn": "<id>"}`. `render.load_encounter(root) -> dict` helper (fails `no_encounter` if absent).

- [ ] **Step 1: Write the failing tests**

`engine/tests/test_grid_render.py`:

```python
import json

from typer.testing import CliRunner

from ttrpg_engine import grid, render, worldfs
from ttrpg_engine.cli import app

runner = CliRunner()

ENC = {
    "id": "skirmish", "name": "Skirmish", "round": 1, "turn": 0,
    "order": ["pc-brin", "goblin-1"],
    "grid": {"width": 6, "height": 4},
    "terrain": [{"type": "wall", "cells": [[3, 0], [3, 1]]},
                {"type": "difficult", "cells": [[4, 3]]}],
    "positions": {"pc-brin": [1, 1], "goblin-1": [5, 2]},
    "monsters": {"goblin-1": {"type": "goblin", "name": "Goblin 1", "hp": 7, "dead": False}},
}


def test_chebyshev():
    assert grid.chebyshev((0, 0), (3, 4)) == 4
    assert grid.chebyshev((2, 2), (2, 2)) == 0


def test_blocked():
    assert grid.blocked(ENC, (3, 0)) == "wall"
    assert grid.blocked(ENC, (6, 0)) == "oob"
    assert grid.blocked(ENC, (5, 2)) == "occupied"
    assert grid.blocked(ENC, (0, 0)) is None


def test_ascii_map_contents():
    art = render.ascii_map(ENC)
    assert "B" in art and "g" in art and "#" in art and "~" in art
    assert "B=pc-brin" in art and "g=goblin-1" in art
    row1 = art.splitlines()[2]        # header is line 0, row y=0 is line 1
    assert row1.split()[1:][1] == "B"  # x=1 on row y=1


def test_cli_render(wroot):
    worldfs.write_yaml(wroot / "state" / "encounter.yaml", ENC)
    res = runner.invoke(app, ["map", "render"])
    data = json.loads(res.stdout)
    assert data["round"] == 1 and data["turn"] == "pc-brin"
    assert "#" in data["map"]


def test_cli_render_no_encounter(wroot):
    res = runner.invoke(app, ["map", "render"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "no_encounter"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd engine && uv run pytest tests/test_grid_render.py -q`
Expected: FAIL — missing modules.

- [ ] **Step 3: Implement**

`engine/src/ttrpg_engine/grid.py`:

```python
def chebyshev(a: tuple[int, int], b: tuple[int, int]) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def cells_of(enc: dict, terrain_type: str) -> set[tuple[int, int]]:
    out = set()
    for feature in enc.get("terrain", []):
        if feature["type"] == terrain_type:
            out.update(tuple(c) for c in feature["cells"])
    return out


def blocked(enc: dict, cell: tuple[int, int]) -> str | None:
    x, y = cell
    if not (0 <= x < enc["grid"]["width"] and 0 <= y < enc["grid"]["height"]):
        return "oob"
    if cell in cells_of(enc, "wall"):
        return "wall"
    for cid, pos in enc["positions"].items():
        if tuple(pos) == cell and not enc["monsters"].get(cid, {}).get("dead", False):
            return "occupied"
    return None
```

`engine/src/ttrpg_engine/render.py`:

```python
from pathlib import Path

from ttrpg_engine import grid, worldfs
from ttrpg_engine.errors import EngineError


def load_encounter(root: Path) -> dict:
    path = root / "state" / "encounter.yaml"
    if not path.exists():
        raise EngineError("no_encounter", "no active encounter")
    return worldfs.read_yaml(path)


def symbols(enc: dict) -> dict[str, str]:
    """Deterministic map of combatant id -> single glyph."""
    out, used = {}, set()
    for cid in enc["order"]:
        is_pc = cid.startswith("pc-")
        glyph = cid.removeprefix("pc-")[0]
        glyph = glyph.upper() if is_pc else glyph.lower()
        while glyph in used:  # collision: walk the alphabet
            nxt = chr(ord(glyph) + 1)
            glyph = nxt if nxt.isalpha() else ("A" if is_pc else "a")
        used.add(glyph)
        out[cid] = glyph
    return out


def ascii_map(enc: dict) -> str:
    w, h = enc["grid"]["width"], enc["grid"]["height"]
    syms = symbols(enc)
    cells = [["." for _ in range(w)] for _ in range(h)]
    for x, y in grid.cells_of(enc, "wall"):
        cells[y][x] = "#"
    for x, y in grid.cells_of(enc, "difficult"):
        cells[y][x] = "~"
    for cid, pos in enc["positions"].items():
        if enc["monsters"].get(cid, {}).get("dead", False):
            continue
        x, y = pos
        cells[y][x] = syms[cid]
    header = "   " + " ".join(str(x % 10) for x in range(w))
    rows = [f"{y:2d} " + " ".join(cells[y]) for y in range(h)]
    legend = "  ".join(f"{glyph}={cid}" for cid, glyph in syms.items())
    return "\n".join([header, *rows, "", legend, "#=wall  ~=difficult"])
```

Add to `engine/src/ttrpg_engine/cli.py`:

```python
from ttrpg_engine import render

map_app = typer.Typer()
app.add_typer(map_app, name="map")


@map_app.command("render")
def map_render(svg: bool = typer.Option(False, "--svg")):
    root = require_root()
    enc = guard(render.load_encounter, root)
    payload = {"map": render.ascii_map(enc), "round": enc["round"],
               "turn": enc["order"][enc["turn"]]}
    if svg:
        payload["svg"] = str(guard(render.write_svg, root, enc))
    emit(payload)
```

(`render.write_svg` arrives in Task 8; until then don't pass `--svg`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd engine && uv run pytest -q`
Expected: all PASS (Task 8's `--svg` path is untested so the missing function is fine).

- [ ] **Step 5: Commit**

```bash
git add engine
git commit -m "feat(engine): sparse grid math and ASCII map render"
```

---

### Task 8: SVG render + `renders/index.html` gallery

**Files:**
- Modify: `engine/src/ttrpg_engine/render.py`
- Test: `engine/tests/test_svg.py`

**Interfaces:**
- Consumes: encounter schema, `worldfs.read_yaml`, clock state, `render.symbols`.
- Produces: `render.svg_map(enc: dict) -> str` (self-contained `<svg>`; 40px cells, light grid lines, dark rects for walls, tan for difficult, blue circles + white initial for PCs, red for monsters, title + legend text); `render.write_svg(root: Path, enc: dict) -> Path` (writes `renders/<date>-<encounter-id>-r<round:02d>.svg`, then regenerates `renders/index.html` listing every `*.svg` newest-first with `<h3>` stamp + `<img src>`); wired into `engine map render --svg` (done in Task 7).

- [ ] **Step 1: Write the failing tests**

`engine/tests/test_svg.py`:

```python
import json

from typer.testing import CliRunner

from ttrpg_engine import render, worldfs
from ttrpg_engine.cli import app
from .test_grid_render import ENC

runner = CliRunner()


def test_svg_contains_tokens_and_walls():
    svg = render.svg_map(ENC)
    assert svg.startswith("<svg")
    assert svg.count("<circle") == 2          # one PC, one live monster
    assert "pc-brin" in svg


def test_write_svg_stamps_and_indexes(wroot):
    worldfs.write_yaml(wroot / "state" / "encounter.yaml", ENC)
    res = runner.invoke(app, ["map", "render", "--svg"])
    assert res.exit_code == 0, res.stdout
    path = json.loads(res.stdout)["svg"]
    assert path.endswith("1203-04-17-skirmish-r01.svg")
    index = (wroot / "renders" / "index.html").read_text()
    assert "1203-04-17-skirmish-r01.svg" in index


def test_dead_monsters_not_drawn():
    enc = json.loads(json.dumps(ENC))
    enc["monsters"]["goblin-1"]["dead"] = True
    assert render.svg_map(enc).count("<circle") == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd engine && uv run pytest tests/test_svg.py -q`
Expected: FAIL — `render.svg_map` missing.

- [ ] **Step 3: Implement**

Append to `engine/src/ttrpg_engine/render.py`:

```python
_CELL = 40


def svg_map(enc: dict) -> str:
    w, h = enc["grid"]["width"], enc["grid"]["height"]
    W, H = w * _CELL, h * _CELL + 30
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
             f'viewBox="0 0 {W} {H}" font-family="monospace">',
             f'<rect width="{W}" height="{H}" fill="#fafaf7"/>']
    for x, y in grid.cells_of(enc, "difficult"):
        parts.append(f'<rect x="{x*_CELL}" y="{y*_CELL}" width="{_CELL}" height="{_CELL}" fill="#d8c9a3"/>')
    for x, y in grid.cells_of(enc, "wall"):
        parts.append(f'<rect x="{x*_CELL}" y="{y*_CELL}" width="{_CELL}" height="{_CELL}" fill="#44403c"/>')
    for i in range(w + 1):
        parts.append(f'<line x1="{i*_CELL}" y1="0" x2="{i*_CELL}" y2="{h*_CELL}" stroke="#ccc"/>')
    for i in range(h + 1):
        parts.append(f'<line x1="0" y1="{i*_CELL}" x2="{w*_CELL}" y2="{i*_CELL}" stroke="#ccc"/>')
    syms = symbols(enc)
    for cid, pos in enc["positions"].items():
        if enc["monsters"].get(cid, {}).get("dead", False):
            continue
        x, y = pos
        cx, cy = x * _CELL + _CELL // 2, y * _CELL + _CELL // 2
        color = "#2563eb" if cid.startswith("pc-") else "#dc2626"
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="{_CELL//2 - 4}" fill="{color}"/>')
        parts.append(f'<text x="{cx}" y="{cy + 5}" text-anchor="middle" fill="#fff">{syms[cid]}</text>')
    legend = "   ".join(f"{s}={cid}" for cid, s in syms.items())
    parts.append(f'<text x="4" y="{h*_CELL + 20}" font-size="12">{enc["name"]} — round {enc["round"]} — {legend}</text>')
    parts.append("</svg>")
    return "".join(parts)


def write_svg(root: Path, enc: dict) -> Path:
    clk = worldfs.read_yaml(worldfs.state(root, "clock"))
    stem = f'{clk["date"]}-{enc["id"]}-r{enc["round"]:02d}'
    out = root / "renders" / f"{stem}.svg"
    out.parent.mkdir(exist_ok=True)
    out.write_text(svg_map(enc))
    entries = [f'<h3>{f.stem}</h3><img src="{f.name}" style="max-width:100%">'
               for f in sorted(out.parent.glob("*.svg"), reverse=True)]
    (out.parent / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>Battle maps</title>'
        '<body style="font-family:monospace;max-width:720px;margin:2rem auto">'
        + "".join(entries) + "</body>")
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd engine && uv run pytest -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add engine
git commit -m "feat(engine): SVG battle-map renders with index.html gallery"
```

---

### Task 9: Encounter lifecycle (`engine encounter start/next/end`)

**Files:**
- Create: `engine/src/ttrpg_engine/combat.py`
- Modify: `engine/src/ttrpg_engine/cli.py`
- Test: `engine/tests/test_encounter.py`

**Interfaces:**
- Consumes: encounter maps in `canon/maps/encounters/*.yaml` (schema in fixture `skirmish.yaml`), bestiary via `game.bestiary_entry`, party sheets, `render.load_encounter`, `timeline`, `dice`, `chargen.attr_mod`.
- Produces: `combat.start(root, g, map_rel: str, rng) -> dict` (spawns monster instances `<type>-N`, seats PCs on `pc_spawns` in party order, rolls initiative d20+DEX-mod per combatant, writes encounter, appends `encounter` event); `combat.next_turn(root) -> dict` (advances `turn`; wraps to new `round` and then decrements every positive effect duration, dropping expired; returns `{round, turn, up, expired_effects}`); `combat.end(root, g, rng) -> dict` (sums XP over all monsters, splits floor-equally among PCs — remainder to first member, rolls each monster's `loot.gold`, adds gold + items to `party.gold`/`party.stash`, deletes `state/encounter.yaml`, appends `encounter` event; returns `{xp_each, gold, items}`); `combat.get_combatant(root, enc, cid) -> tuple[str, dict]` (kind `"pc"`/`"monster"`; monster dict is live in `enc`, PC sheet is read fresh from disk); `combat.save_pc(root, sheet)`; `combat.save_encounter(root, enc)`. Commands: `engine encounter start MAP_REL` (path relative to `canon/`, e.g. `maps/encounters/skirmish.yaml`), `engine encounter next`, `engine encounter end`.

- [ ] **Step 1: Write the failing tests**

`engine/tests/test_encounter.py`:

```python
import json

from typer.testing import CliRunner

from ttrpg_engine import worldfs
from ttrpg_engine.cli import app
from .conftest import make_pc

runner = CliRunner()


def start(seed="5"):
    make_pc()
    res = runner.invoke(app, ["--seed", seed, "encounter", "start",
                              "maps/encounters/skirmish.yaml"])
    assert res.exit_code == 0, res.stdout
    return json.loads(res.stdout)


def test_start_seats_and_orders(wroot):
    data = start()
    enc = worldfs.read_yaml(wroot / "state" / "encounter.yaml")
    assert set(enc["order"]) == {"pc-borin", "goblin-1", "goblin-2"}
    assert enc["positions"]["pc-borin"] == [1, 3]          # first spawn
    assert enc["monsters"]["goblin-1"]["hp"] == 7
    assert data["order"] == enc["order"]
    assert enc["round"] == 1 and enc["turn"] == 0


def test_next_wraps_and_ticks_effects(wroot):
    start()
    enc = worldfs.read_yaml(wroot / "state" / "encounter.yaml")
    enc["monsters"]["goblin-1"]["effects"] = [{"name": "blessed", "duration": 1}]
    worldfs.write_yaml(wroot / "state" / "encounter.yaml", enc)
    for _ in range(3):                                     # 3 combatants -> full round
        res = runner.invoke(app, ["encounter", "next"])
    data = json.loads(res.stdout)
    assert data["round"] == 2 and data["expired_effects"] == [["goblin-1", "blessed"]]


def test_end_awards_xp_and_loot(wroot):
    start()
    res = runner.invoke(app, ["--seed", "2", "encounter", "end"])
    data = json.loads(res.stdout)
    assert data["xp_each"] == 100                          # 2 goblins * 50 / 1 PC
    sheet = worldfs.read_yaml(wroot / "state" / "party" / "pc-borin.yaml")
    assert sheet["xp"] == 100
    party = worldfs.read_yaml(wroot / "state" / "party.yaml")
    assert party["gold"] == data["gold"] > 0
    assert not (wroot / "state" / "encounter.yaml").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd engine && uv run pytest tests/test_encounter.py -q`
Expected: FAIL — no module `ttrpg_engine.combat`.

- [ ] **Step 3: Implement**

`engine/src/ttrpg_engine/combat.py`:

```python
from pathlib import Path
from random import Random

from ttrpg_engine import dice, timeline, worldfs
from ttrpg_engine.chargen import attr_mod
from ttrpg_engine.errors import EngineError
from ttrpg_engine.game import bestiary_entry
from ttrpg_engine.render import load_encounter


def save_encounter(root: Path, enc: dict) -> None:
    worldfs.write_yaml(root / "state" / "encounter.yaml", enc)


def save_pc(root: Path, sheet: dict) -> None:
    worldfs.write_yaml(worldfs.state(root, f"party/{sheet['id']}"), sheet)


def get_combatant(root: Path, enc: dict, cid: str) -> tuple[str, dict]:
    if cid in enc["monsters"]:
        return "monster", enc["monsters"][cid]
    path = worldfs.state(root, f"party/{cid}")
    if path.exists():
        return "pc", worldfs.read_yaml(path)
    raise EngineError("not_found", f"no combatant {cid}")


def start(root: Path, g: dict, map_rel: str, rng: Random) -> dict:
    if (root / "state" / "encounter.yaml").exists():
        raise EngineError("encounter_active", "an encounter is already running")
    emap = worldfs.read_yaml(root / "canon" / map_rel)
    party = worldfs.read_yaml(worldfs.state(root, "party"))
    if not party["members"]:
        raise EngineError("no_party", "no PCs in the party")
    if len(party["members"]) > len(emap["pc_spawns"]):
        raise EngineError("map_invalid", "not enough pc_spawns for the party")
    monsters, positions, counts = {}, {}, {}
    for spec in emap["monsters"]:
        mtype = spec["type"]
        counts[mtype] = counts.get(mtype, 0) + 1
        mid = f"{mtype}-{counts[mtype]}"
        entry = bestiary_entry(g, mtype)
        monsters[mid] = {"type": mtype, "name": f"{entry['name']} {counts[mtype]}",
                         "ac": entry["ac"], "hp": entry["hp"], "max_hp": entry["hp"],
                         "speed": entry["speed"], "attributes": entry["attributes"],
                         "attacks": entry["attacks"], "xp": entry["xp"],
                         "loot": entry.get("loot", {"gold": None, "items": []}),
                         "effects": [], "dead": False}
        positions[mid] = list(spec["pos"])
    for pc_id, spawn in zip(party["members"], emap["pc_spawns"]):
        positions[pc_id] = list(spawn)
    scores = {}
    for cid in [*party["members"], *monsters]:
        _, data = get_combatant(root, {"monsters": monsters}, cid)
        dex = data["attributes"]["DEX"]
        scores[cid] = (rng.randint(1, 20) + attr_mod(dex), dex, cid)
    order = sorted(scores, key=lambda c: scores[c], reverse=True)
    enc = {"id": emap["id"], "name": emap["name"], "round": 1, "turn": 0,
           "order": order, "grid": emap["grid"], "terrain": emap.get("terrain", []),
           "positions": positions, "monsters": monsters}
    save_encounter(root, enc)
    timeline.append_event(root, type_="encounter", actors=order,
                          summary=f"encounter started: {emap['name']}")
    return {"id": enc["id"], "order": order,
            "initiative": {c: scores[c][0] for c in order}}


def next_turn(root: Path) -> dict:
    enc = load_encounter(root)
    enc["turn"] += 1
    expired = []
    if enc["turn"] >= len(enc["order"]):
        enc["turn"] = 0
        enc["round"] += 1
        for cid in enc["order"]:
            kind, data = get_combatant(root, enc, cid)
            keep = []
            for eff in data.get("effects", []):
                if eff["duration"] > 0:
                    eff["duration"] -= 1
                if eff["duration"] == 0:
                    expired.append([cid, eff["name"]])
                else:
                    keep.append(eff)
            data["effects"] = keep
            if kind == "pc":
                save_pc(root, data)
    save_encounter(root, enc)
    return {"round": enc["round"], "turn": enc["turn"],
            "up": enc["order"][enc["turn"]], "expired_effects": expired}


def end(root: Path, g: dict, rng: Random) -> dict:
    enc = load_encounter(root)
    party = worldfs.read_yaml(worldfs.state(root, "party"))
    total_xp = sum(m["xp"] for m in enc["monsters"].values())
    xp_each = total_xp // len(party["members"])
    for i, pc_id in enumerate(party["members"]):
        sheet = worldfs.read_yaml(worldfs.state(root, f"party/{pc_id}"))
        sheet["xp"] += xp_each + (total_xp % len(party["members"]) if i == 0 else 0)
        save_pc(root, sheet)
    gold, items = 0, []
    for m in enc["monsters"].values():
        loot = m.get("loot") or {}
        if loot.get("gold"):
            gold += dice.roll(loot["gold"], rng).total
        items.extend(loot.get("items", []))
    party["gold"] += gold
    party["stash"].extend(items)
    worldfs.write_yaml(worldfs.state(root, "party"), party)
    (root / "state" / "encounter.yaml").unlink()
    timeline.append_event(root, type_="encounter",
                          summary=f"encounter ended: {enc['name']} (+{total_xp} xp, +{gold} gp)",
                          delta={"party": {"gold": gold}})
    return {"xp_each": xp_each, "gold": gold, "items": items}
```

Add to `engine/src/ttrpg_engine/cli.py`:

```python
from ttrpg_engine import combat

enc_app = typer.Typer()
app.add_typer(enc_app, name="encounter")


@enc_app.command("start")
def encounter_start(map_rel: str):
    root = require_root()
    g = guard(worldfs.load_game_for, root)
    emit(guard(combat.start, root, g, map_rel, rng))


@enc_app.command("next")
def encounter_next():
    emit(guard(combat.next_turn, require_root()))


@enc_app.command("end")
def encounter_end():
    root = require_root()
    g = guard(worldfs.load_game_for, root)
    emit(guard(combat.end, root, g, rng))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd engine && uv run pytest -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add engine
git commit -m "feat(engine): encounter lifecycle with initiative, effect ticks, xp and loot"
```

---

### Task 10: Attack, damage, healing, death (`engine attack/damage/heal/effect/deathsave`)

**Files:**
- Modify: `engine/src/ttrpg_engine/combat.py`, `engine/src/ttrpg_engine/cli.py`
- Test: `engine/tests/test_attack.py`

**Interfaces:**
- Consumes: `combat.get_combatant/save_pc/save_encounter`, `render.load_encounter`, `dice`, `timeline`, `cli.d20_roll`.
- Produces: `combat.resolve_actor(root, cid) -> tuple[str, dict, dict | None]` (kind, data, enc-or-None — works outside encounters for PCs); `combat.attack(root, attacker: str, target: str, *, attack_name: str | None, adv: bool, dis: bool, roll_fn, rng) -> dict` (natural 1 auto-misses, natural 20 auto-hits and rolls the damage dice twice adding the modifier once; range-checked via `grid.chebyshev` when both have positions); `combat.apply_damage(root, target: str, amount: int, source: str) -> dict` (monster at 0 hp → `dead: true`; PC at 0 hp → effects `unconscious` + `dying` (duration -1) and `death_saves: {successes: 0, fails: 0}` added to sheet); `combat.apply_heal(root, target, amount, source) -> dict` (caps at max_hp; healing above 0 clears unconscious/dying/death_saves); `combat.set_effect(root, target, name, duration) -> dict` / `combat.remove_effect(root, target, name) -> dict`; `combat.death_save(root, actor, *, roll_fn) -> dict` (DC 10; nat 20 → regain 1 hp; 3 fails → `dead` effect + `death` event; 3 successes → stable: dying cleared, still unconscious). All mutations append timeline events. Commands: `engine attack --attacker A --target B [--attack name] [--adv|--dis]`, `engine damage --target T --amount N --source TXT`, `engine heal --target T --amount N --source TXT`, `engine effect add --target T --name N --duration D`, `engine effect remove --target T --name N`, `engine deathsave --actor P`.

- [ ] **Step 1: Write the failing tests**

`engine/tests/test_attack.py`:

```python
import json

from typer.testing import CliRunner

from ttrpg_engine import combat, worldfs
from ttrpg_engine.cli import app
from .conftest import make_pc

runner = CliRunner()


def fixed(nat):
    return lambda mod, adv, dis: (nat, nat + mod)


def setup_fight(wroot):
    make_pc()
    res = runner.invoke(app, ["--seed", "5", "encounter", "start",
                              "maps/encounters/skirmish.yaml"])
    assert res.exit_code == 0, res.stdout
    # put attacker adjacent to goblin-1 so range checks pass
    enc = worldfs.read_yaml(wroot / "state" / "encounter.yaml")
    enc["positions"]["pc-borin"] = [8, 4]
    worldfs.write_yaml(wroot / "state" / "encounter.yaml", enc)


def test_attack_hit_and_crit(wroot):
    import random
    setup_fight(wroot)
    rng = random.Random(1)
    r = combat.attack(wroot, "pc-borin", "goblin-1", attack_name=None,
                      adv=False, dis=False, roll_fn=fixed(15), rng=rng)
    assert r["hit"] is True and r["damage"] >= 3       # 1d8+2
    enc = worldfs.read_yaml(wroot / "state" / "encounter.yaml")
    assert enc["monsters"]["goblin-1"]["hp"] == 7 - r["damage"] or enc["monsters"]["goblin-1"]["dead"]
    r2 = combat.attack(wroot, "pc-borin", "goblin-2", attack_name=None,
                       adv=False, dis=False, roll_fn=fixed(20), rng=rng)
    assert r2["crit"] == "hit" and r2["damage"] >= 4   # two damage dice + mod


def test_nat1_misses_even_vs_ac0(wroot):
    import random
    setup_fight(wroot)
    enc = worldfs.read_yaml(wroot / "state" / "encounter.yaml")
    enc["monsters"]["goblin-1"]["ac"] = 0
    worldfs.write_yaml(wroot / "state" / "encounter.yaml", enc)
    r = combat.attack(wroot, "pc-borin", "goblin-1", attack_name=None,
                      adv=False, dis=False, roll_fn=fixed(1), rng=random.Random(1))
    assert r["hit"] is False and r["damage"] == 0


def test_out_of_range_fails(wroot):
    setup_fight(wroot)
    res = runner.invoke(app, ["attack", "--attacker", "goblin-2", "--target", "pc-borin"])
    assert res.exit_code == 1                           # goblin-2 at [10,4], pc at [8,4], range 1
    assert json.loads(res.stdout)["error"]["code"] == "out_of_range"


def test_pc_drops_to_dying_then_death_saves(wroot):
    setup_fight(wroot)
    combat.apply_damage(wroot, "pc-borin", 99, source="test")
    sheet = worldfs.read_yaml(wroot / "state" / "party" / "pc-borin.yaml")
    assert sheet["hp"] == 0
    names = {e["name"] for e in sheet["effects"]}
    assert {"unconscious", "dying"} <= names
    r = combat.death_save(wroot, "pc-borin", roll_fn=fixed(20))
    sheet = worldfs.read_yaml(wroot / "state" / "party" / "pc-borin.yaml")
    assert r["result"] == "revived" and sheet["hp"] == 1 and sheet["effects"] == []
    combat.apply_damage(wroot, "pc-borin", 99, source="test")
    for _ in range(3):
        r = combat.death_save(wroot, "pc-borin", roll_fn=fixed(2))
    assert r["result"] == "dead"
    sheet = worldfs.read_yaml(wroot / "state" / "party" / "pc-borin.yaml")
    assert "dead" in {e["name"] for e in sheet["effects"]}


def test_heal_clears_dying(wroot):
    setup_fight(wroot)
    combat.apply_damage(wroot, "pc-borin", 99, source="test")
    combat.apply_heal(wroot, "pc-borin", 5, source="potion")
    sheet = worldfs.read_yaml(wroot / "state" / "party" / "pc-borin.yaml")
    assert sheet["hp"] == 5 and sheet["effects"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd engine && uv run pytest tests/test_attack.py -q`
Expected: FAIL — `combat.attack` missing.

- [ ] **Step 3: Implement**

Append to `engine/src/ttrpg_engine/combat.py`:

```python
from ttrpg_engine import grid


def resolve_actor(root: Path, cid: str):
    enc = None
    if (root / "state" / "encounter.yaml").exists():
        enc = load_encounter(root)
    if enc and cid in enc["monsters"]:
        return "monster", enc["monsters"][cid], enc
    path = worldfs.state(root, f"party/{cid}")
    if path.exists():
        return "pc", worldfs.read_yaml(path), enc
    raise EngineError("not_found", f"no combatant {cid}")


def _persist(root, kind, data, enc):
    if kind == "pc":
        save_pc(root, data)
        if enc is not None:
            save_encounter(root, enc)
    else:
        save_encounter(root, enc)


def apply_damage(root: Path, target: str, amount: int, source: str) -> dict:
    kind, data, enc = resolve_actor(root, target)
    before = data["hp"]
    data["hp"] = max(0, before - amount)
    dropped = data["hp"] == 0 and before > 0
    if dropped:
        if kind == "monster":
            data["dead"] = True
        else:
            names = {e["name"] for e in data["effects"]}
            data["effects"] += [{"name": n, "duration": -1}
                                for n in ("unconscious", "dying") if n not in names]
            data["death_saves"] = {"successes": 0, "fails": 0}
    _persist(root, kind, data, enc)
    timeline.append_event(root, type_="damage", actors=[target],
                          summary=f"{target} takes {amount} damage ({source})",
                          delta={target: {"hp": [before, data["hp"]]}})
    return {"target": target, "amount": amount, "hp": [before, data["hp"]],
            "dropped": dropped}


def apply_heal(root: Path, target: str, amount: int, source: str) -> dict:
    kind, data, enc = resolve_actor(root, target)
    before = data["hp"]
    data["hp"] = min(data["max_hp"], before + amount)
    if kind == "pc" and data["hp"] > 0:
        data["effects"] = [e for e in data["effects"]
                           if e["name"] not in ("unconscious", "dying")]
        data.pop("death_saves", None)
    _persist(root, kind, data, enc)
    timeline.append_event(root, type_="heal", actors=[target],
                          summary=f"{target} heals {amount} ({source})",
                          delta={target: {"hp": [before, data["hp"]]}})
    return {"target": target, "amount": amount, "hp": [before, data["hp"]]}


def attack(root: Path, attacker: str, target: str, *, attack_name: str | None,
           adv: bool, dis: bool, roll_fn, rng: Random) -> dict:
    _, a_data, enc = resolve_actor(root, attacker)
    _, t_data, _ = resolve_actor(root, target)
    attacks = a_data["attacks"]
    atk = next((a for a in attacks if a["name"] == attack_name), attacks[0] if attacks else None)
    if atk is None:
        raise EngineError("no_attack", f"{attacker} has no attack {attack_name!r}")
    if enc and attacker in enc["positions"] and target in enc["positions"]:
        dist = grid.chebyshev(tuple(enc["positions"][attacker]),
                              tuple(enc["positions"][target]))
        if dist > atk.get("range", 1):
            raise EngineError("out_of_range",
                              f"{target} is {dist} away, range is {atk.get('range', 1)}")
    natural, total = roll_fn(atk["attack_mod"], adv, dis)
    crit = "hit" if natural == 20 else "fumble" if natural == 1 else None
    hit = natural != 1 and (natural == 20 or total >= t_data["ac"])
    damage = 0
    if hit:
        dmg = dice.roll(str(atk["damage"]), rng)
        damage = dmg.total
        if crit == "hit":
            damage += sum(dice.roll(str(atk["damage"]), rng).rolls)  # dice again, modifier once
    result = {"attacker": attacker, "target": target, "attack": atk["name"],
              "natural": natural, "total": total, "vs_ac": t_data["ac"],
              "hit": hit, "crit": crit, "damage": damage}
    verb = "hits" if hit else "misses"
    timeline.append_event(root, type_="attack", actors=[attacker, target],
                          summary=f"{attacker} {verb} {target} with {atk['name']}"
                                  + (f" for {damage}" if hit else ""))
    if hit and damage:
        dmg_result = apply_damage(root, target, damage, source=f"{attacker}:{atk['name']}")
        result["target_hp"] = dmg_result["hp"]
        result["dropped"] = dmg_result["dropped"]
    return result


def set_effect(root: Path, target: str, name: str, duration: int) -> dict:
    kind, data, enc = resolve_actor(root, target)
    data["effects"] = [e for e in data["effects"] if e["name"] != name]
    data["effects"].append({"name": name, "duration": duration})
    _persist(root, kind, data, enc)
    timeline.append_event(root, type_="effect", actors=[target],
                          summary=f"{target} gains {name} ({duration} rounds)")
    return {"target": target, "effects": data["effects"]}


def remove_effect(root: Path, target: str, name: str) -> dict:
    kind, data, enc = resolve_actor(root, target)
    data["effects"] = [e for e in data["effects"] if e["name"] != name]
    _persist(root, kind, data, enc)
    timeline.append_event(root, type_="effect", actors=[target],
                          summary=f"{target} loses {name}")
    return {"target": target, "effects": data["effects"]}


def death_save(root: Path, actor: str, *, roll_fn) -> dict:
    kind, sheet, enc = resolve_actor(root, actor)
    if kind != "pc" or "dying" not in {e["name"] for e in sheet["effects"]}:
        raise EngineError("not_dying", f"{actor} is not dying")
    natural, _ = roll_fn(0, False, False)
    saves = sheet.setdefault("death_saves", {"successes": 0, "fails": 0})
    if natural == 20:
        result = "revived"
    elif natural >= 10:
        saves["successes"] += 1
        result = "stable" if saves["successes"] >= 3 else "success"
    else:
        saves["fails"] += 1
        result = "dead" if saves["fails"] >= 3 else "fail"
    if result == "revived":
        sheet["hp"] = 1
        sheet["effects"] = [e for e in sheet["effects"]
                            if e["name"] not in ("unconscious", "dying")]
        sheet.pop("death_saves", None)
    elif result == "stable":
        sheet["effects"] = [e for e in sheet["effects"] if e["name"] != "dying"]
        sheet.pop("death_saves", None)
    elif result == "dead":
        sheet["effects"].append({"name": "dead", "duration": -1})
    _persist(root, kind, sheet, enc)
    timeline.append_event(root, type_="deathsave", actors=[actor],
                          summary=f"{actor} death save: {natural} -> {result}")
    if result == "dead":
        timeline.append_event(root, type_="death", actors=[actor],
                              summary=f"{actor} has died")
    return {"actor": actor, "natural": natural, "result": result,
            "saves": sheet.get("death_saves")}
```

Add to `engine/src/ttrpg_engine/cli.py`:

```python
effect_app = typer.Typer()
app.add_typer(effect_app, name="effect")


@app.command()
def attack(
    attacker: str = typer.Option(...),
    target: str = typer.Option(...),
    attack_name: str | None = typer.Option(None, "--attack"),
    adv: bool = typer.Option(False, "--adv"),
    dis: bool = typer.Option(False, "--dis"),
):
    root = require_root()
    emit(guard(combat.attack, root, attacker, target, attack_name=attack_name,
               adv=adv, dis=dis, roll_fn=d20_roll, rng=rng))


@app.command()
def damage(target: str = typer.Option(...), amount: int = typer.Option(...),
           source: str = typer.Option("GM")):
    emit(guard(combat.apply_damage, require_root(), target, amount, source))


@app.command()
def heal(target: str = typer.Option(...), amount: int = typer.Option(...),
         source: str = typer.Option("GM")):
    emit(guard(combat.apply_heal, require_root(), target, amount, source))


@effect_app.command("add")
def effect_add(target: str = typer.Option(...), name: str = typer.Option(...),
               duration: int = typer.Option(-1)):
    emit(guard(combat.set_effect, require_root(), target, name, duration))


@effect_app.command("remove")
def effect_remove(target: str = typer.Option(...), name: str = typer.Option(...)):
    emit(guard(combat.remove_effect, require_root(), target, name))


@app.command()
def deathsave(actor: str = typer.Option(...)):
    emit(guard(combat.death_save, require_root(), actor, roll_fn=d20_roll))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd engine && uv run pytest -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add engine
git commit -m "feat(engine): attacks, damage, healing, effects, death saves"
```

---

### Task 11: Movement (`engine move`)

**Files:**
- Modify: `engine/src/ttrpg_engine/combat.py`, `engine/src/ttrpg_engine/cli.py`
- Test: `engine/tests/test_move.py`

**Interfaces:**
- Consumes: `grid.chebyshev/blocked/cells_of`, encounter state, `timeline`.
- Produces: `combat.move(root, actor: str, to: tuple[int, int], *, force: bool = False) -> dict`. Cost model (documented v1 simplification — no pathfinding): `cost = chebyshev(from, to)`, `+1` if the destination is difficult terrain; must be `<= speed`; destination must not be `blocked()` (oob/wall/occupied). `force=True` skips cost and occupancy checks (GM repositioning) but never allows oob. Appends `move` event. Command `engine move --actor A --to X,Y [--force]`.

- [ ] **Step 1: Write the failing tests**

`engine/tests/test_move.py`:

```python
import json

from typer.testing import CliRunner

from ttrpg_engine import worldfs
from ttrpg_engine.cli import app
from .test_attack import setup_fight

runner = CliRunner()


def test_move_ok_and_updates_position(wroot):
    setup_fight(wroot)                       # pc-borin at [8,4], speed 5 (dwarf)
    res = runner.invoke(app, ["move", "--actor", "pc-borin", "--to", "5,4"])
    assert res.exit_code == 0, res.stdout
    data = json.loads(res.stdout)
    assert data["to"] == [5, 4] and data["cost"] == 3
    enc = worldfs.read_yaml(wroot / "state" / "encounter.yaml")
    assert enc["positions"]["pc-borin"] == [5, 4]


def test_move_too_far_rejected(wroot):
    setup_fight(wroot)
    res = runner.invoke(app, ["move", "--actor", "pc-borin", "--to", "0,0"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "too_far"


def test_move_into_wall_rejected_difficult_costs_extra(wroot):
    setup_fight(wroot)
    res = runner.invoke(app, ["move", "--actor", "pc-borin", "--to", "4,1"])
    assert json.loads(res.stdout)["error"]["code"] == "blocked"
    res = runner.invoke(app, ["move", "--actor", "pc-borin", "--to", "7,5"])
    assert json.loads(res.stdout)["cost"] == 2           # chebyshev 1 + difficult 1


def test_force_ignores_cost(wroot):
    setup_fight(wroot)
    res = runner.invoke(app, ["move", "--actor", "pc-borin", "--to", "0,0", "--force"])
    assert res.exit_code == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd engine && uv run pytest tests/test_move.py -q`
Expected: FAIL — `combat.move` missing.

- [ ] **Step 3: Implement**

Append to `engine/src/ttrpg_engine/combat.py`:

```python
def move(root: Path, actor: str, to: tuple[int, int], *, force: bool = False) -> dict:
    enc = load_encounter(root)
    if actor not in enc["positions"]:
        raise EngineError("not_found", f"{actor} is not on the map")
    src = tuple(enc["positions"][actor])
    to = tuple(to)
    reason = grid.blocked(enc, to)
    if reason == "oob" or (reason and not force):
        raise EngineError("blocked", f"cannot enter {list(to)}: {reason}")
    _, data, _ = resolve_actor(root, actor)
    cost = grid.chebyshev(src, to)
    if to in grid.cells_of(enc, "difficult"):
        cost += 1
    if not force and cost > data["speed"]:
        raise EngineError("too_far", f"cost {cost} exceeds speed {data['speed']}")
    enc["positions"][actor] = list(to)
    save_encounter(root, enc)
    timeline.append_event(root, type_="move", actors=[actor],
                          summary=f"{actor} moves {list(src)} -> {list(to)}")
    return {"actor": actor, "from": list(src), "to": list(to),
            "cost": cost, "forced": force}
```

Add to `engine/src/ttrpg_engine/cli.py`:

```python
@app.command()
def move(actor: str = typer.Option(...), to: str = typer.Option(..., help="X,Y"),
         force: bool = typer.Option(False, "--force")):
    try:
        x, y = (int(v) for v in to.split(","))
    except ValueError:
        fail("bad_coord", f"--to must be X,Y, got {to!r}")
    emit(guard(combat.move, require_root(), actor, (x, y), force=force))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd engine && uv run pytest -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add engine
git commit -m "feat(engine): grid movement with speed and terrain costs"
```

---

### Task 12: Spellcasting (`engine cast`)

**Files:**
- Create: `engine/src/ttrpg_engine/spells.py`
- Modify: `engine/src/ttrpg_engine/cli.py`
- Test: `engine/tests/test_spells.py`

**Interfaces:**
- Consumes: spell schema (fixture `spells.yaml`), `combat.resolve_actor/apply_damage/apply_heal/set_effect`, `chargen.attr_mod`, `grid.chebyshev`, `dice`, `timeline`.
- Produces: `spells.cast(root, g, caster: str, spell_name: str, target: str | None, *, roll_fn, rng) -> dict`. Rules: caster must be a PC that knows the spell; level > 0 requires and consumes one `spell_slots[level].current`; `CASTMOD` in damage/heal expressions is replaced with the caster's `cast_attr` modifier (`expr.replace("+CASTMOD", f"{mod:+d}")`); resolve `attack` → spell attack vs target AC with mod `proficiency + castmod`; `save` → target rolls d20 + `attr_mod(save_attr)` vs DC `8 + proficiency + castmod`, `on_save: none` → no damage on save, `on_save: half` → half; `auto` → always lands. If a spell has `heal` → `apply_heal`; `damage` → `apply_damage`; `effect` → `set_effect`. Range checked when an encounter is active and both are positioned. Appends `cast` event before any damage/heal events. Command `engine cast --caster P --spell S [--target T]` (target defaults to caster).

- [ ] **Step 1: Write the failing tests**

`engine/tests/test_spells.py`:

```python
import json
import random

from typer.testing import CliRunner

from ttrpg_engine import combat, spells, worldfs
from ttrpg_engine.cli import app
from .conftest import make_pc
from .test_attack import fixed

runner = CliRunner()

CLERIC = dict(name="Mira", cls="cleric", race="human",
              assign="WIS=15,CON=14,STR=13,DEX=12,INT=10,CHA=8",
              skills="insight,medicine")


def test_cure_wounds_consumes_slot_and_heals(wroot):
    make_pc(**CLERIC)
    combat.apply_damage(wroot, "pc-mira", 5, source="test")
    res = runner.invoke(app, ["--seed", "4", "cast", "--caster", "pc-mira",
                              "--spell", "cure_wounds", "--target", "pc-mira"])
    assert res.exit_code == 0, res.stdout
    data = json.loads(res.stdout)
    assert data["healed"] >= 1 + 3                     # 1d8 + WIS mod (16 -> +3)
    sheet = worldfs.read_yaml(wroot / "state" / "party" / "pc-mira.yaml")
    assert sheet["spell_slots"][1]["current"] == 1


def test_no_slots_left_fails(wroot):
    make_pc(**CLERIC)
    for _ in range(2):
        runner.invoke(app, ["cast", "--caster", "pc-mira", "--spell", "cure_wounds"])
    res = runner.invoke(app, ["cast", "--caster", "pc-mira", "--spell", "cure_wounds"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "no_slots"


def test_save_spell_damage_and_on_save_none(wroot):
    make_pc(**CLERIC)
    res = runner.invoke(app, ["--seed", "9", "encounter", "start",
                              "maps/encounters/skirmish.yaml"])
    assert res.exit_code == 0
    r = spells.cast(wroot, worldfs.load_game_for(wroot), "pc-mira", "sacred_flame",
                    "goblin-1", roll_fn=fixed(1), rng=random.Random(1))
    assert r["save"]["success"] is False               # nat 1 + DEX mod 2 = 3 < DC 13
    assert r["damage"] >= 1
    r2 = spells.cast(wroot, worldfs.load_game_for(wroot), "pc-mira", "sacred_flame",
                     "goblin-1", roll_fn=fixed(20), rng=random.Random(1))
    assert r2["save"]["success"] is True and r2["damage"] == 0


def test_unknown_spell_fails(wroot):
    make_pc(**CLERIC)
    res = runner.invoke(app, ["cast", "--caster", "pc-mira", "--spell", "fireball"])
    assert json.loads(res.stdout)["error"]["code"] == "unknown_spell"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd engine && uv run pytest tests/test_spells.py -q`
Expected: FAIL — no module `ttrpg_engine.spells`.

- [ ] **Step 3: Implement**

`engine/src/ttrpg_engine/spells.py`:

```python
from pathlib import Path
from random import Random

from ttrpg_engine import combat, dice, grid, timeline, worldfs
from ttrpg_engine.chargen import attr_mod
from ttrpg_engine.errors import EngineError


def _expr(template: str, castmod: int) -> str:
    return str(template).replace("+CASTMOD", f"{castmod:+d}")


def cast(root: Path, g: dict, caster: str, spell_name: str, target: str | None,
         *, roll_fn, rng: Random) -> dict:
    kind, sheet, enc = combat.resolve_actor(root, caster)
    if kind != "pc":
        raise EngineError("not_pc", "only PCs cast via their sheets in v1")
    if spell_name not in g["spells"]:
        raise EngineError("unknown_spell", f"no spell {spell_name}")
    if spell_name not in sheet["spells_known"]:
        raise EngineError("unknown_spell", f"{caster} does not know {spell_name}")
    spell = g["spells"][spell_name]
    cast_attr = g["classes"][sheet["class"]]["cast_attr"]
    castmod = attr_mod(sheet["attributes"][cast_attr])
    level = spell["level"]
    if level > 0:
        slot = sheet["spell_slots"].get(level)
        if not slot or slot["current"] < 1:
            raise EngineError("no_slots", f"no level-{level} slots left")
        slot["current"] -= 1
        combat.save_pc(root, sheet)
    target = target or caster
    _, t_data, _ = combat.resolve_actor(root, target)
    if enc and caster in enc["positions"] and target in enc["positions"]:
        dist = grid.chebyshev(tuple(enc["positions"][caster]),
                              tuple(enc["positions"][target]))
        if dist > spell["range"]:
            raise EngineError("out_of_range", f"{target} is {dist} away, range {spell['range']}")
    result = {"caster": caster, "spell": spell_name, "target": target,
              "slot_level": level or None, "damage": 0, "healed": 0}
    lands, half = True, False
    if spell["resolve"] == "attack":
        natural, total = roll_fn(sheet["proficiency"] + castmod, False, False)
        lands = natural != 1 and (natural == 20 or total >= t_data["ac"])
        result["attack"] = {"natural": natural, "total": total, "vs_ac": t_data["ac"], "hit": lands}
    elif spell["resolve"] == "save":
        dc = 8 + sheet["proficiency"] + castmod
        natural, _ = roll_fn(0, False, False)
        total = natural + attr_mod(t_data["attributes"][spell["save_attr"]])
        saved = total >= dc
        result["save"] = {"attr": spell["save_attr"], "dc": dc, "total": total, "success": saved}
        if saved:
            lands, half = spell.get("on_save", "none") == "half", spell.get("on_save") == "half"
    timeline.append_event(root, type_="cast", actors=[caster, target],
                          summary=f"{caster} casts {spell_name} at {target}")
    if lands:
        if "damage" in spell:
            dmg = dice.roll(_expr(spell["damage"], castmod), rng).total
            dmg = max(1, dmg // 2) if half else dmg
            result["damage"] = combat.apply_damage(root, target, dmg,
                                                   source=f"{caster}:{spell_name}")["amount"]
        if "heal" in spell:
            amount = dice.roll(_expr(spell["heal"], castmod), rng).total
            result["healed"] = combat.apply_heal(root, target, amount,
                                                 source=f"{caster}:{spell_name}")["amount"]
        if "effect" in spell:
            combat.set_effect(root, target, spell["effect"]["name"],
                              spell["effect"]["duration"])
            result["effect"] = spell["effect"]
    return result
```

Add to `engine/src/ttrpg_engine/cli.py`:

```python
from ttrpg_engine import spells


@app.command()
def cast(caster: str = typer.Option(...), spell: str = typer.Option(...),
         target: str | None = typer.Option(None)):
    root = require_root()
    g = guard(worldfs.load_game_for, root)
    emit(guard(spells.cast, root, g, caster, spell, target, roll_fn=d20_roll, rng=rng))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd engine && uv run pytest -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add engine
git commit -m "feat(engine): spellcasting with slots, saves, and spell attacks"
```

---

### Task 13: Rest and recovery (`engine rest`)

**Files:**
- Create: `engine/src/ttrpg_engine/rest.py`
- Modify: `engine/src/ttrpg_engine/cli.py`
- Test: `engine/tests/test_rest.py`

**Interfaces:**
- Consumes: `clock.advance`, sheets, `g["recovery"]`, `g["classes"][cls]["hit_die"]`, `dice`, `timeline`.
- Produces: `rest.take(root, g, kind: str, rng) -> dict` (`kind` in `short|long`; fails `encounter_active` if an encounter exists; **short** (1h): each living PC heals `roll(hit_die) + CON mod` (min 1), capped at max; **long** (8h): full HP, all `spell_slots.current = max`, all effects cleared, `death_saves` removed — dead PCs are untouched by either). Advances the clock by the rest's hours, appends one `rest` event. Command `engine rest --type short|long`.

- [ ] **Step 1: Write the failing tests**

`engine/tests/test_rest.py`:

```python
import json

from typer.testing import CliRunner

from ttrpg_engine import combat, worldfs
from ttrpg_engine.cli import app
from .conftest import make_pc
from .test_spells import CLERIC

runner = CliRunner()


def test_short_rest_heals_and_advances_clock(wroot):
    make_pc()
    combat.apply_damage(wroot, "pc-borin", 6, source="test")
    res = runner.invoke(app, ["--seed", "8", "rest", "--type", "short"])
    assert res.exit_code == 0, res.stdout
    sheet = worldfs.read_yaml(wroot / "state" / "party" / "pc-borin.yaml")
    assert 13 - 6 < sheet["hp"] <= 13
    clock = worldfs.read_yaml(wroot / "state" / "clock.yaml")
    assert clock["hour"] == 10


def test_long_rest_restores_everything(wroot):
    make_pc(**CLERIC)
    runner.invoke(app, ["cast", "--caster", "pc-mira", "--spell", "cure_wounds"])
    combat.apply_damage(wroot, "pc-mira", 4, source="test")
    combat.set_effect(wroot, "pc-mira", "poisoned", -1)
    res = runner.invoke(app, ["rest", "--type", "long"])
    assert res.exit_code == 0, res.stdout
    sheet = worldfs.read_yaml(wroot / "state" / "party" / "pc-mira.yaml")
    assert sheet["hp"] == sheet["max_hp"]
    assert sheet["spell_slots"][1]["current"] == 2
    assert sheet["effects"] == []
    clock = worldfs.read_yaml(wroot / "state" / "clock.yaml")
    assert clock["hour"] == 17


def test_rest_blocked_in_encounter(wroot):
    make_pc()
    runner.invoke(app, ["--seed", "5", "encounter", "start", "maps/encounters/skirmish.yaml"])
    res = runner.invoke(app, ["rest", "--type", "short"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "encounter_active"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd engine && uv run pytest tests/test_rest.py -q`
Expected: FAIL — no module `ttrpg_engine.rest`.

- [ ] **Step 3: Implement**

`engine/src/ttrpg_engine/rest.py`:

```python
from pathlib import Path
from random import Random

from ttrpg_engine import clock as clock_mod
from ttrpg_engine import dice, timeline, worldfs
from ttrpg_engine.chargen import attr_mod
from ttrpg_engine.errors import EngineError


def take(root: Path, g: dict, kind: str, rng: Random) -> dict:
    if kind not in ("short", "long"):
        raise EngineError("bad_rest", "type must be short or long")
    if (root / "state" / "encounter.yaml").exists():
        raise EngineError("encounter_active", "cannot rest mid-encounter")
    hours = g["recovery"][f"{kind}_rest"]["hours"]
    party = worldfs.read_yaml(worldfs.state(root, "party"))
    healed = {}
    for pc_id in party["members"]:
        sheet = worldfs.read_yaml(worldfs.state(root, f"party/{pc_id}"))
        if "dead" in {e["name"] for e in sheet["effects"]}:
            continue
        before = sheet["hp"]
        if kind == "short":
            hit_die = g["classes"][sheet["class"]]["hit_die"]
            gain = max(1, dice.roll(f"d{hit_die}", rng).total
                       + attr_mod(sheet["attributes"]["CON"]))
            sheet["hp"] = min(sheet["max_hp"], sheet["hp"] + gain)
        else:
            sheet["hp"] = sheet["max_hp"]
            for slot in sheet["spell_slots"].values():
                slot["current"] = slot["max"]
            sheet["effects"] = []
            sheet.pop("death_saves", None)
        healed[pc_id] = [before, sheet["hp"]]
        worldfs.write_yaml(worldfs.state(root, f"party/{pc_id}"), sheet)
    clk = clock_mod.advance(worldfs.read_yaml(worldfs.state(root, "clock")), hours)
    worldfs.write_yaml(worldfs.state(root, "clock"), clk)
    timeline.append_event(root, type_="rest", actors=list(healed),
                          summary=f"the party takes a {kind} rest ({hours}h)",
                          delta={p: {"hp": hp} for p, hp in healed.items()})
    return {"type": kind, "hours": hours, "healed": healed, "clock": clk}
```

Add to `engine/src/ttrpg_engine/cli.py`:

```python
from ttrpg_engine import rest as rest_mod


@app.command()
def rest(type_: str = typer.Option(..., "--type")):
    root = require_root()
    g = guard(worldfs.load_game_for, root)
    emit(guard(rest_mod.take, root, g, type_, rng))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd engine && uv run pytest -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add engine
git commit -m "feat(engine): short and long rests"
```

---

### Task 14: Travel (`engine travel`)

**Files:**
- Create: `engine/src/ttrpg_engine/travel.py`
- Modify: `engine/src/ttrpg_engine/cli.py`
- Test: `engine/tests/test_travel.py`

**Interfaces:**
- Consumes: `canon/maps/region.yaml` (world's copy — the GM may have edited it, so read from `canon/`, never from the game dir), `clock.advance`, `party.location`, `timeline`.
- Produces: `travel.go(root, dest: str) -> dict` (fails `encounter_active` mid-combat, `unknown_node` for a bad id, `no_route` when no edge connects current↔dest; otherwise advances clock by the edge's `hours`, sets `party.location`, appends `travel` event; returns `{from, to, hours, clock}`). Command `engine travel --to NODE`.

- [ ] **Step 1: Write the failing tests**

`engine/tests/test_travel.py`:

```python
import json

from typer.testing import CliRunner

from ttrpg_engine import worldfs
from ttrpg_engine.cli import app

runner = CliRunner()


def test_travel_moves_party_and_clock(wroot):
    res = runner.invoke(app, ["travel", "--to", "cave"])
    assert res.exit_code == 0, res.stdout
    data = json.loads(res.stdout)
    assert data["from"] == "town" and data["to"] == "cave" and data["hours"] == 4
    party = worldfs.read_yaml(wroot / "state" / "party.yaml")
    assert party["location"] == "cave"
    assert worldfs.read_yaml(wroot / "state" / "clock.yaml")["hour"] == 13


def test_travel_rejects_unconnected_and_unknown(wroot):
    res = runner.invoke(app, ["travel", "--to", "atlantis"])
    assert json.loads(res.stdout)["error"]["code"] == "unknown_node"
    runner.invoke(app, ["travel", "--to", "cave"])
    res = runner.invoke(app, ["travel", "--to", "cave"])
    assert json.loads(res.stdout)["error"]["code"] == "no_route"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd engine && uv run pytest tests/test_travel.py -q`
Expected: FAIL — no module `ttrpg_engine.travel`.

- [ ] **Step 3: Implement**

`engine/src/ttrpg_engine/travel.py`:

```python
from pathlib import Path

from ttrpg_engine import clock as clock_mod
from ttrpg_engine import timeline, worldfs
from ttrpg_engine.errors import EngineError


def go(root: Path, dest: str) -> dict:
    if (root / "state" / "encounter.yaml").exists():
        raise EngineError("encounter_active", "cannot travel mid-encounter")
    region = worldfs.read_yaml(root / "canon" / "maps" / "region.yaml")
    party = worldfs.read_yaml(worldfs.state(root, "party"))
    here = party["location"]
    if dest not in region["nodes"]:
        raise EngineError("unknown_node", f"no node {dest}")
    if dest == here:
        raise EngineError("no_route", f"already at {dest}")
    edge = next((e for e in region["edges"] if set(e["between"]) == {here, dest}), None)
    if edge is None:
        raise EngineError("no_route", f"no route {here} -> {dest}")
    clk = clock_mod.advance(worldfs.read_yaml(worldfs.state(root, "clock")), edge["hours"])
    worldfs.write_yaml(worldfs.state(root, "clock"), clk)
    party["location"] = dest
    worldfs.write_yaml(worldfs.state(root, "party"), party)
    timeline.append_event(root, type_="travel",
                          summary=f"party travels {here} -> {dest} ({edge['hours']}h)")
    return {"from": here, "to": dest, "hours": edge["hours"], "clock": clk}
```

Add to `engine/src/ttrpg_engine/cli.py`:

```python
from ttrpg_engine import travel as travel_mod


@app.command()
def travel(to: str = typer.Option(...)):
    emit(guard(travel_mod.go, require_root(), to))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd engine && uv run pytest -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add engine
git commit -m "feat(engine): node-graph travel with clock advance"
```

---

### Task 15: Inventory and gold (`engine item`, `engine gold`)

**Files:**
- Create: `engine/src/ttrpg_engine/inventory.py`
- Modify: `engine/src/ttrpg_engine/cli.py`
- Test: `engine/tests/test_inventory.py`

**Interfaces:**
- Consumes: sheets, `party.yaml` (party pool: `gold` + `stash`), `g["items"]`, `timeline`.
- Produces: `inventory.add_item(root, g, actor: str, item: str, qty: int) -> dict` (item must exist in `g["items"]`; merges into existing inventory line); `inventory.remove_item(root, g, actor, item, qty) -> dict` (fails `not_enough`); `inventory.adjust_gold(root, target: str, amount: int) -> dict` (`target` = pc id or `"party"`; negative amounts spend; fails `not_enough` below 0). All append `item`/`gold` events. Commands: `engine item add --actor P --item I [--qty N]`, `engine item remove --actor P --item I [--qty N]`, `engine gold add --amount N [--actor P|--party]`, `engine gold spend --amount N [--actor P|--party]`.

- [ ] **Step 1: Write the failing tests**

`engine/tests/test_inventory.py`:

```python
import json

from typer.testing import CliRunner

from ttrpg_engine import worldfs
from ttrpg_engine.cli import app
from .conftest import make_pc

runner = CliRunner()


def test_item_add_merges_and_remove(wroot):
    pc = make_pc()
    runner.invoke(app, ["item", "add", "--actor", pc, "--item", "torch", "--qty", "2"])
    res = runner.invoke(app, ["item", "add", "--actor", pc, "--item", "torch", "--qty", "3"])
    assert res.exit_code == 0, res.stdout
    sheet = worldfs.read_yaml(wroot / "state" / "party" / f"{pc}.yaml")
    assert {"item": "torch", "qty": 5} in sheet["inventory"]
    res = runner.invoke(app, ["item", "remove", "--actor", pc, "--item", "torch", "--qty", "9"])
    assert json.loads(res.stdout)["error"]["code"] == "not_enough"


def test_unknown_item_rejected(wroot):
    pc = make_pc()
    res = runner.invoke(app, ["item", "add", "--actor", pc, "--item", "vorpal_sword"])
    assert json.loads(res.stdout)["error"]["code"] == "unknown_item"


def test_gold_pc_and_party(wroot):
    pc = make_pc()
    runner.invoke(app, ["gold", "spend", "--amount", "4", "--actor", pc])
    sheet = worldfs.read_yaml(wroot / "state" / "party" / f"{pc}.yaml")
    assert sheet["gold"] == 6                      # fighter starts with 10
    res = runner.invoke(app, ["gold", "spend", "--amount", "999", "--party"])
    assert json.loads(res.stdout)["error"]["code"] == "not_enough"
    runner.invoke(app, ["gold", "add", "--amount", "50", "--party"])
    party = worldfs.read_yaml(wroot / "state" / "party.yaml")
    assert party["gold"] == 50
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd engine && uv run pytest tests/test_inventory.py -q`
Expected: FAIL — no module `ttrpg_engine.inventory`.

- [ ] **Step 3: Implement**

`engine/src/ttrpg_engine/inventory.py`:

```python
from pathlib import Path

from ttrpg_engine import timeline, worldfs
from ttrpg_engine.errors import EngineError


def _sheet(root: Path, actor: str) -> dict:
    return worldfs.read_yaml(worldfs.state(root, f"party/{actor}"))


def add_item(root: Path, g: dict, actor: str, item: str, qty: int) -> dict:
    if item not in g["items"]:
        raise EngineError("unknown_item", f"no item {item} in this game")
    sheet = _sheet(root, actor)
    line = next((l for l in sheet["inventory"] if l["item"] == item), None)
    if line:
        line["qty"] += qty
    else:
        sheet["inventory"].append({"item": item, "qty": qty})
    worldfs.write_yaml(worldfs.state(root, f"party/{actor}"), sheet)
    timeline.append_event(root, type_="item", actors=[actor],
                          summary=f"{actor} gains {qty}x {item}")
    return {"actor": actor, "inventory": sheet["inventory"]}


def remove_item(root: Path, g: dict, actor: str, item: str, qty: int) -> dict:
    sheet = _sheet(root, actor)
    line = next((l for l in sheet["inventory"] if l["item"] == item), None)
    if line is None or line["qty"] < qty:
        raise EngineError("not_enough", f"{actor} does not have {qty}x {item}")
    line["qty"] -= qty
    sheet["inventory"] = [l for l in sheet["inventory"] if l["qty"] > 0]
    worldfs.write_yaml(worldfs.state(root, f"party/{actor}"), sheet)
    timeline.append_event(root, type_="item", actors=[actor],
                          summary=f"{actor} loses {qty}x {item}")
    return {"actor": actor, "inventory": sheet["inventory"]}


def adjust_gold(root: Path, target: str, amount: int) -> dict:
    if target == "party":
        data = worldfs.read_yaml(worldfs.state(root, "party"))
    else:
        data = _sheet(root, target)
    if data["gold"] + amount < 0:
        raise EngineError("not_enough", f"{target} has only {data['gold']} gp")
    before = data["gold"]
    data["gold"] += amount
    path = worldfs.state(root, "party" if target == "party" else f"party/{target}")
    worldfs.write_yaml(path, data)
    verb = "gains" if amount >= 0 else "spends"
    timeline.append_event(root, type_="gold", actors=[] if target == "party" else [target],
                          summary=f"{target} {verb} {abs(amount)} gp",
                          delta={target: {"gold": [before, data["gold"]]}})
    return {"target": target, "gold": data["gold"]}
```

Add to `engine/src/ttrpg_engine/cli.py`:

```python
from ttrpg_engine import inventory

item_app = typer.Typer()
gold_app = typer.Typer()
app.add_typer(item_app, name="item")
app.add_typer(gold_app, name="gold")


@item_app.command("add")
def item_add(actor: str = typer.Option(...), item: str = typer.Option(...),
             qty: int = typer.Option(1)):
    root = require_root()
    g = guard(worldfs.load_game_for, root)
    emit(guard(inventory.add_item, root, g, actor, item, qty))


@item_app.command("remove")
def item_remove(actor: str = typer.Option(...), item: str = typer.Option(...),
                qty: int = typer.Option(1)):
    root = require_root()
    g = guard(worldfs.load_game_for, root)
    emit(guard(inventory.remove_item, root, g, actor, item, qty))


def _gold_target(actor: str | None, party: bool) -> str:
    if party == (actor is not None):
        fail("bad_target", "pass exactly one of --actor or --party")
    return "party" if party else actor


@gold_app.command("add")
def gold_add(amount: int = typer.Option(...), actor: str | None = typer.Option(None),
             party: bool = typer.Option(False, "--party")):
    emit(guard(inventory.adjust_gold, require_root(), _gold_target(actor, party), amount))


@gold_app.command("spend")
def gold_spend(amount: int = typer.Option(...), actor: str | None = typer.Option(None),
               party: bool = typer.Option(False, "--party")):
    emit(guard(inventory.adjust_gold, require_root(), _gold_target(actor, party), -amount))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd engine && uv run pytest -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add engine
git commit -m "feat(engine): inventory and gold management"
```

---

### Task 16: XP and leveling (`engine xp grant`, `engine level up`)

**Files:**
- Create: `engine/src/ttrpg_engine/level.py`
- Modify: `engine/src/ttrpg_engine/cli.py`
- Test: `engine/tests/test_level.py`

**Interfaces:**
- Consumes: sheets, `g["progression"]` (`xp_thresholds`, `proficiency`, `max_level`), class level rows, `dice`, `timeline`.
- Produces: `level.grant_xp(root, amount: int, reason: str) -> dict` (grants `amount` to **each** living party member, appends one `xp` event); `level.up(root, g, actor: str, rng) -> dict` (fails `not_ready` if `xp < xp_thresholds[level+1]`, `max_level` at cap; on success: `level += 1`, `max_hp/hp += max(1, roll(hit_die) + CON mod)`, merges new row's `features` and `spells`, sets `spell_slots` to the row's `slots` (new max, current topped up by the gained max delta), updates `proficiency`; appends `level` event). Commands: `engine xp grant --amount N --reason TXT`, `engine level up --actor P`.

- [ ] **Step 1: Write the failing tests**

`engine/tests/test_level.py`:

```python
import json

from typer.testing import CliRunner

from ttrpg_engine import worldfs
from ttrpg_engine.cli import app
from .conftest import make_pc
from .test_spells import CLERIC

runner = CliRunner()


def test_grant_and_levelup_cleric(wroot):
    make_pc(**CLERIC)
    res = runner.invoke(app, ["level", "up", "--actor", "pc-mira"])
    assert json.loads(res.stdout)["error"]["code"] == "not_ready"
    runner.invoke(app, ["xp", "grant", "--amount", "300", "--reason", "quest"])
    res = runner.invoke(app, ["--seed", "6", "level", "up", "--actor", "pc-mira"])
    assert res.exit_code == 0, res.stdout
    sheet = worldfs.read_yaml(wroot / "state" / "party" / "pc-mira.yaml")
    assert sheet["level"] == 2
    assert sheet["max_hp"] >= 11                       # 8+2 at L1, +>=1
    assert "bless" in sheet["spells_known"]
    assert sheet["spell_slots"][1]["max"] == 3
    assert sheet["spell_slots"][1]["current"] == 3     # was full, +1 max


def test_level_cap(wroot):
    make_pc(**CLERIC)
    runner.invoke(app, ["xp", "grant", "--amount", "9999", "--reason", "test"])
    runner.invoke(app, ["--seed", "1", "level", "up", "--actor", "pc-mira"])
    runner.invoke(app, ["--seed", "1", "level", "up", "--actor", "pc-mira"])
    res = runner.invoke(app, ["--seed", "1", "level", "up", "--actor", "pc-mira"])
    assert json.loads(res.stdout)["error"]["code"] == "max_level"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd engine && uv run pytest tests/test_level.py -q`
Expected: FAIL — no module `ttrpg_engine.level`.

- [ ] **Step 3: Implement**

`engine/src/ttrpg_engine/level.py`:

```python
from pathlib import Path
from random import Random

from ttrpg_engine import dice, timeline, worldfs
from ttrpg_engine.chargen import attr_mod
from ttrpg_engine.errors import EngineError


def grant_xp(root: Path, amount: int, reason: str) -> dict:
    party = worldfs.read_yaml(worldfs.state(root, "party"))
    granted = []
    for pc_id in party["members"]:
        sheet = worldfs.read_yaml(worldfs.state(root, f"party/{pc_id}"))
        if "dead" in {e["name"] for e in sheet["effects"]}:
            continue
        sheet["xp"] += amount
        worldfs.write_yaml(worldfs.state(root, f"party/{pc_id}"), sheet)
        granted.append(pc_id)
    timeline.append_event(root, type_="xp", actors=granted,
                          summary=f"+{amount} xp each ({reason})")
    return {"amount": amount, "granted": granted}


def up(root: Path, g: dict, actor: str, rng: Random) -> dict:
    sheet = worldfs.read_yaml(worldfs.state(root, f"party/{actor}"))
    prog = g["progression"]
    new_level = sheet["level"] + 1
    if new_level > prog["max_level"]:
        raise EngineError("max_level", f"{actor} is already at max level {prog['max_level']}")
    threshold = prog["xp_thresholds"][new_level]
    if sheet["xp"] < threshold:
        raise EngineError("not_ready", f"needs {threshold} xp, has {sheet['xp']}")
    cls = g["classes"][sheet["class"]]
    row = cls["levels"][new_level]
    gain = max(1, dice.roll(f"d{cls['hit_die']}", rng).total
               + attr_mod(sheet["attributes"]["CON"]))
    sheet["level"] = new_level
    sheet["max_hp"] += gain
    sheet["hp"] += gain
    sheet["proficiency"] = prog["proficiency"][new_level]
    sheet["features"] += [f for f in row["features"] if f not in sheet["features"]]
    sheet["spells_known"] += [s for s in row["spells"] if s not in sheet["spells_known"]]
    for lvl, n in row["slots"].items():
        slot = sheet["spell_slots"].setdefault(lvl, {"max": 0, "current": 0})
        slot["current"] += n - slot["max"]
        slot["max"] = n
    worldfs.write_yaml(worldfs.state(root, f"party/{actor}"), sheet)
    timeline.append_event(root, type_="level", actors=[actor],
                          summary=f"{actor} reaches level {new_level} (+{gain} hp)")
    return {"actor": actor, "level": new_level, "hp_gain": gain,
            "features": sheet["features"], "spells_known": sheet["spells_known"]}
```

Add to `engine/src/ttrpg_engine/cli.py`:

```python
from ttrpg_engine import level as level_mod

xp_app = typer.Typer()
level_app = typer.Typer()
app.add_typer(xp_app, name="xp")
app.add_typer(level_app, name="level")


@xp_app.command("grant")
def xp_grant(amount: int = typer.Option(...), reason: str = typer.Option("")):
    emit(guard(level_mod.grant_xp, require_root(), amount, reason))


@level_app.command("up")
def level_up(actor: str = typer.Option(...)):
    root = require_root()
    g = guard(worldfs.load_game_for, root)
    emit(guard(level_mod.up, root, g, actor, rng))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd engine && uv run pytest -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add engine
git commit -m "feat(engine): xp grants and leveling"
```

---

### Task 17: Reference game — ruleset content (`games/reference/`)

**Files:**
- Create: `games/reference/game.yaml`, `games/reference/ruleset/*` (same file set as the fixture minigame), `games/reference/content/` (placeholder dirs only — content arrives in Task 18)
- Test: `engine/tests/test_reference_game.py`

**Interfaces:**
- Consumes: every schema from Task 2's fixture (the fixture IS the schema contract).
- Produces: the complete four-class ruleset later tasks instantiate worlds from. Validation gate: `engine game validate games/reference` passes once Task 18 adds content.

This is content authoring, not engine work — the implementer writes fresh YAML following the fixture schemas exactly. Required contents (all four classes must satisfy `engine game validate`):

- `game.yaml`: `name: reference`, `version: 0.1.0`, `start_date: "1203-04-17"`, `start_hour: 9`, `start_location: thornbury`.
- `ruleset/core.yaml`, `attributes.yaml`, `combat.yaml`, `recovery.yaml`, `progression.yaml`, `economy.yaml`: copy the fixture values verbatim (they are the reference values; the fixture was derived from this design).
- `ruleset/races.yaml` — four races: `human {bonuses: {CON: 1, WIS: 1}, speed: 6}`, `elf {bonuses: {DEX: 2}, speed: 6}`, `dwarf {bonuses: {CON: 2}, speed: 5}`, `halfling {bonuses: {DEX: 1, CHA: 1}, speed: 5}`.
- `ruleset/classes/` — four classes, levels 1–3 each. Fixed mechanical frame (hit die, cast attr, gear); the implementer fills features/spells rows sensibly:
  - `fighter.yaml`: hit_die 10, cast_attr null, gear `[chain_mail, longsword]`, gold 10, skill_choices 2, skills `[athletics, intimidation, perception, survival]`.
  - `rogue.yaml`: hit_die 8, cast_attr null, gear `[leather_armor, dagger, dagger]`, gold 15, features include `sneak_attack` at 1, skill_choices 3, skills `[stealth, perception, deception, acrobatics, sleight_of_hand]`.
  - `cleric.yaml`: hit_die 8, cast_attr WIS, gear `[leather_armor, mace]`, gold 15, skill_choices 2, skills `[insight, medicine, persuasion, religion]`, slots `{1: {1: 2}, 2: {1: 3}, 3: {1: 4}}` (per-level rows), spells from the cleric list below.
  - `wizard.yaml`: hit_die 6, cast_attr INT, gear `[dagger]`, gold 20, skill_choices 2, skills `[arcana, investigation, history, insight]`, same slot ladder, spells from the wizard list below.

  (The skill lists are load-bearing: Task 21's e2e test picks `athletics,perception` / `stealth,perception,deception` / `insight,medicine` / `arcana,investigation`.)
- `ruleset/spells.yaml` — at least: cantrips `fire_bolt` (wizard, attack, 1d10, range 24), `sacred_flame` (cleric, save DEX, 1d8, range 12); level 1 `magic_missile` (wizard, auto, 3d4+3, range 24), `sleep_dust` (wizard, save WIS, effect unconscious 2 rounds, on_save none, range 12), `cure_wounds` (cleric, auto heal 1d8+CASTMOD, range 1), `bless` (cleric, auto, effect blessed 10 rounds, range 6), `shield_of_faith` (cleric, auto, effect shielded 10 rounds, range 6). All names/prose written fresh.
- `ruleset/effects.yaml` — `blessed`, `shielded`, `poisoned`, `unconscious`, `dying`, `dead`, `prone`, `frightened`, each with a one-line `impact` note telling the GM how to adjudicate (e.g. which side gets `--adv`/`--dis`).
- `ruleset/items.yaml` — weapons (`longsword 1d8`, `mace 1d6`, `dagger 1d4 finesse`, `shortbow 1d6 finesse range 16`), armor (`leather_armor 11+dex`, `chain_mail 16`), gear (`torch`, `rope`, `healing_potion {type: consumable, heal: 2d4+2, price: 50}`, `thieves_tools`), all priced.

- [ ] **Step 1: Write the failing test**

`engine/tests/test_reference_game.py`:

```python
from pathlib import Path

from ttrpg_engine import game

REFERENCE = Path(__file__).resolve().parents[2] / "games" / "reference"


def test_reference_game_validates():
    assert REFERENCE.exists(), "games/reference missing"
    assert game.validate(REFERENCE) == []


def test_reference_has_four_classes_and_races():
    g = game.load(REFERENCE)
    assert set(g["classes"]) == {"fighter", "rogue", "cleric", "wizard"}
    assert set(g["races"]) == {"human", "elf", "dwarf", "halfling"}
    for cls in g["classes"].values():
        assert set(cls["levels"]) == {1, 2, 3}
```

(Path note: from `engine/tests/test_reference_game.py`, `parents[0]` is `tests/`, `parents[1]` is `engine/`, `parents[2]` is the repo root.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd engine && uv run pytest tests/test_reference_game.py -q`
Expected: FAIL — `games/reference missing`.

- [ ] **Step 3: Author the ruleset**

Write every file listed above. Follow fixture schemas field-for-field; validate iteratively:

Run: `cd engine && uv run engine game validate ../games/reference`
Expected once content/ exists (Task 18): `{"valid": true, ...}`. Until then the validator reports the missing region map — that specific error is acceptable at this task's gate; assert the rest is clean.

Adjust the test gate for this task: `test_reference_game_validates` may be marked `@pytest.mark.xfail(reason="content lands in task 18")` — remove the mark in Task 18.

- [ ] **Step 4: Run tests**

Run: `cd engine && uv run pytest tests/test_reference_game.py -q`
Expected: `test_reference_has_four_classes_and_races` PASS; validation test xfail.

- [ ] **Step 5: Commit**

```bash
git add games engine/tests/test_reference_game.py
git commit -m "feat(games): reference ruleset - four classes, races, spells, items"
```

---

### Task 18: Reference game — v1 adventure content

**Files:**
- Create: `games/reference/content/maps/region.yaml`, `games/reference/content/maps/encounters/*.yaml`, `games/reference/content/bestiary/*.yaml`, `games/reference/content/npcs.yaml`, `games/reference/content/factions.yaml`, `games/reference/content/history.md`, `games/reference/content/adventure.md`
- Modify: `engine/tests/test_reference_game.py` (drop the xfail)

**Interfaces:**
- Consumes: fixture content schemas (region map, encounter map, bestiary), `game.validate`.
- Produces: the playable v1 adventure: town → travel → dungeon → boss. Node ids and encounter map paths used by Task 21's e2e test: nodes `thornbury`, `old-road`, `barrow-woods`, `barrowdeep`; encounter maps `maps/encounters/road-ambush.yaml`, `maps/encounters/barrow-hall.yaml`, `maps/encounters/kings-tomb.yaml`.

Content requirements (author fresh prose; mechanics follow fixture schemas):

- **Region map** — 4 nodes with coords/terrain: `thornbury` (town, start), `old-road` (waypoint), `barrow-woods` (forest camp), `barrowdeep` (the dungeon). Edges: thornbury↔old-road 4h, old-road↔barrow-woods 3h, barrow-woods↔barrowdeep 1h.
- **Bestiary** — `goblin` (as fixture), `goblin_archer` (ac 12, hp 5, shortbow range 16, xp 50), `barrow_hound` (ac 12, hp 11, bite 1d6+2, xp 100), `barrow_king` (boss: ac 15, hp 30, blade 1d8+3 plus a `frightened` effect attack, xp 450, loot gold 4d10 + item `kings_circlet` — add `kings_circlet {type: treasure, price: 200}` to items.yaml).
- **Encounter maps** — `road-ambush` (2 goblins + 1 goblin_archer, open road with scrub as difficult terrain), `barrow-hall` (2 barrow_hounds, pillared hall: wall clusters), `kings-tomb` (barrow_king + 1 goblin honor guard, small room, difficult rubble). Each 10–14 wide, 8–10 high, 4 `pc_spawns`.
- **NPCs** — at least: `reeve_halda` (quest-giver in thornbury, hires the party to clear the barrow), `innkeep_bram` (rumors), `pedlar_okko` (traveling merchant met at old-road; buys/sells at list price). Each with `location`, `role`, `disposition`, and a `wants` line for NPC simulation.
- **Factions** — `thornbury_moot` (village council) and `barrow_clan` (the goblins) with goals and a relation to each other.
- **history.md** — half a page: why the barrow is dangerous again, who the Barrow King was. Ends with three adventure hooks.
- **adventure.md** — GM outline: expected beats (hire → travel → ambush → camp → dungeon in two encounters → boss → return + reward 100 gp + `xp grant`), suggested DCs using `core.dcs`, and the loot/reward table. This file is canon the GM reads, not engine input.

- [ ] **Step 1: Author all content files** (validate as you go)

Run: `cd engine && uv run engine game validate ../games/reference`
Expected: `{"valid": true, "game": "reference", "errors": []}`

- [ ] **Step 2: Un-xfail the validation test**

Remove the `@pytest.mark.xfail` from `test_reference_game_validates` (Task 17).

- [ ] **Step 3: Run tests**

Run: `cd engine && uv run pytest tests/test_reference_game.py -q`
Expected: all PASS.

- [ ] **Step 4: Smoke the adventure mechanically**

```bash
cd /tmp && rm -rf smoke-world
uv run --project /Users/kp/gh/ky-ttrpg/engine engine world init smoke-world \
  --game /Users/kp/gh/ky-ttrpg/games/reference --name Smoke
cd smoke-world
uv run --project /Users/kp/gh/ky-ttrpg/engine engine char create --name Test --class fighter \
  --race human --assign "STR=15,CON=14,DEX=13,WIS=12,INT=10,CHA=8" --skills athletics,perception
uv run --project /Users/kp/gh/ky-ttrpg/engine engine travel --to old-road
uv run --project /Users/kp/gh/ky-ttrpg/engine engine encounter start maps/encounters/road-ambush.yaml
uv run --project /Users/kp/gh/ky-ttrpg/engine engine map render --svg
```

Expected: each command emits success JSON; the SVG file exists under `renders/`.

- [ ] **Step 5: Commit**

```bash
git add games engine/tests
git commit -m "feat(games): reference adventure - Thornbury and the Barrowdeep"
```

---

### Task 19: GM agent + session/override skills (`.claude/`)

**Files:**
- Create: `.claude/agents/gm.md`, `.claude/skills/gm-session/SKILL.md`, `.claude/skills/gm-override/SKILL.md`

**Interfaces:**
- Consumes: every engine command (Tasks 1–16), world repo layout.
- Produces: the agent and skills a GM session runs with. Launch: `claude --agent gm` from inside a world repo. No engine changes.

- [ ] **Step 1: Write the GM agent**

`.claude/agents/gm.md`:

```markdown
---
name: gm
description: Game master for ky-ttrpg worlds. Runs sessions from inside a world repo.
tools: Bash, Read, Write, Edit, Glob, Grep, Skill
---

You are the game master for a tabletop RPG campaign. The current working
directory is a world repo: `state/` is the mechanical truth, `canon/` is
the narrative truth, `timeline/` is the append-only record.

# Iron rules

1. **You never invent a number.** Every dice roll, attack, check, HP
   change, purchase, rest, and level-up goes through the `engine` CLI.
   If a rule needs a roll, call `engine`; narrate from its JSON output.
2. **You never edit `state/` or `timeline/` files directly.** Only the
   engine writes there. You MAY edit `canon/` (narrative facts) freely.
3. **Positions come from `engine map render`**, not from memory.
4. **GM overrides are explicit.** Only when the operator says
   "GM override" do you deviate from engine output — log it immediately
   with `engine override log --summary "..."`.

# Modes

- **auto-GM** (default): you narrate and adjudicate. Rulings you make
  (DC choices, NPC reactions) are yours; math is the engine's.
- **manual GM**: the operator has said "manual GM". Defer every ruling
  to them; keep doing the paperwork (engine calls, canon updates).
  "auto GM" switches back. Announce mode changes.

# Running play

- Start or resume every session with the gm-session skill.
- Run combat with the gm-combat skill.
- As narrative facts land (an NPC met, a secret revealed, a faction
  stance shifts), update the matching file in `canon/` right away —
  small edits, no ceremony.
- Simulate NPCs from their `canon/npcs.yaml` entries: play their
  `wants`, keep their `disposition` consistent.
- Players with no human: play their PCs earnestly — party banter stays
  short, decisions favor moving play forward.
- Set DCs from `canon`-relevant difficulty: easy 10, medium 13, hard 16
  (from the game's `core.dcs`).
```

- [ ] **Step 2: Write the session skill**

`.claude/skills/gm-session/SKILL.md`:

```markdown
---
name: gm-session
description: Use when starting or resuming a ky-ttrpg play session in a world repo.
---

# Session start / resume

1. Confirm you are in a world repo: `engine state get session` works.
2. Read `world.yaml`, `state/party.yaml`, `state/clock.yaml`, every
   sheet in `state/party/`, and the latest `sessions/session-*/summary.md`
   if one exists.
3. `git status` must be clean. If not, stop and ask the operator.
4. Run `engine session start`. Note the session number N.
5. Create `sessions/session-NNN/transcript.md` with a heading and the
   in-world date; append notable beats to it as play proceeds (bullet
   lines, not verbatim chat).
6. Commit: `git add -A && git commit -m "session NNN start"`.
7. Recap the previous summary to the players in 3-5 sentences, state
   the party's location and date, then open the scene.

Ending a session is the session-end skill — never improvise it.
```

- [ ] **Step 3: Write the override skill**

`.claude/skills/gm-override/SKILL.md`:

```markdown
---
name: gm-override
description: Use when the operator says "GM override", "manual GM", or "auto GM" in a ky-ttrpg session.
---

# GM override handling

**"GM override" + an instruction**: apply exactly what the operator
said, then immediately log it:
`engine override log --summary "<what changed and why>" --actors <ids>`
If it changes mechanical state, make the change through engine
commands (`damage`, `heal`, `item add`, `move --force`, ...) so state
and timeline stay consistent — the override event explains the cause.

**"manual GM"**: switch modes. From now on, before any adjudication
(DC, ruling, NPC decision) ask the operator and use their answer.
Engine paperwork continues unchanged. Confirm: "Manual GM on."

**"auto GM"**: switch back to auto-GM. Confirm: "Auto GM on."

Never infer an override from tone or repetition — the operator must
use the explicit phrase.
```

- [ ] **Step 4: Verify agent loads**

Run from a world repo (any test world): `claude --agent gm --print "Confirm you can see the world. Run: engine state get clock"`
Expected: the agent runs the engine command and reports the clock. (If `--agent` flag syntax differs in the installed Claude Code version, check `claude --help` and adjust the README accordingly, not the agent file.)

- [ ] **Step 5: Commit**

```bash
git add .claude
git commit -m "feat(claude): gm agent, session and override skills"
```

---

### Task 20: Combat + session-end (dreaming) skills

**Files:**
- Create: `.claude/skills/gm-combat/SKILL.md`, `.claude/skills/session-end/SKILL.md`

**Interfaces:**
- Consumes: engine combat commands (Tasks 9–12), canon layout, session dirs from gm-session.
- Produces: the combat loop convention and the formal session close.

- [ ] **Step 1: Write the combat skill**

`.claude/skills/gm-combat/SKILL.md`:

```markdown
---
name: gm-combat
description: Use when combat starts in a ky-ttrpg session - runs the encounter loop through engine commands.
---

# Running combat

1. `engine encounter start <map-rel>` — read back the initiative order.
2. Render every round start: `engine map render --svg`; show the ASCII
   map in a code block. Tell the operator renders/index.html has the
   pretty version.
3. On each turn (order comes from `engine encounter next`):
   - **PC (human player)**: ask for their action; execute it via
     engine commands; narrate the JSON result.
   - **PC (simulated) / monster**: choose a tactically sensible action
     (attack in range; else move toward the nearest threat using
     `engine move`, then attack if now in range), execute, narrate.
   - Attacks: `engine attack --attacker X --target Y [--adv|--dis]`.
     Apply --adv/--dis per the effects on either side (see the game's
     effects.yaml impact notes).
   - Spells: `engine cast --caster X --spell s [--target Y]`.
4. A PC hitting 0 HP starts death saves: `engine deathsave --actor X`
   on each of their turns until revived, stable, or dead.
5. Combat ends when one side is dead, surrendered, or fled:
   `engine encounter end` — report xp and loot from its JSON.
6. Never move a token, change HP, or decide a hit outside the engine.
```

- [ ] **Step 2: Write the session-end (dreaming) skill**

`.claude/skills/session-end/SKILL.md`:

```markdown
---
name: session-end
description: Use when the operator ends a ky-ttrpg session - writes the summary, reconciles canon, prunes dead lore, commits.
---

# Session end — the dreaming pass

Work through all steps; the final commit is the formal session boundary.

1. **Summary.** Write `sessions/session-NNN/summary.md`: 10-20 bullet
   beats, party status line (location, date, HP, level, notable loot),
   open threads. Source: the transcript file plus `timeline/` events
   from this session (`grep -l "session: N" timeline/*.yaml`).
2. **Canon diff.** `git diff <session-start-commit> -- canon/` (the
   commit made by gm-session). Read every changed file end to end.
3. **Reconcile.** Fix contradictions and plot holes the session
   introduced (an NPC in two places, a fact stated both ways) by
   editing `canon/` directly. Autonomy rule: fix and report — do NOT
   ask permission, but list every fix in your end-of-session report to
   the operator. Escalate (ask, don't fix) only when a fix would alter
   something load-bearing: a PC's history, a quest outcome, anything a
   player explicitly cared about.
4. **Prune.** Remove canon detail that will never matter again
   (the fifth description of the same corridor, one-off flavor NPCs
   with no thread attached). Compress to a line rather than delete
   when unsure. Git history keeps everything recoverable.
5. **Never touch** `state/` or `timeline/` in this pass. If step 3
   found a mechanical inconsistency, log it:
   `engine override log --summary "dreaming: <issue>"` and tell the
   operator — the fix is theirs to make next session.
6. **Commit** everything as one commit:
   `git add -A && git commit -m "session NNN: <one-line summary>"`.
7. Report to the operator: the summary, every reconciliation made,
   everything pruned, anything escalated.
```

- [ ] **Step 3: Manual verification**

In a test world, run one mock session (session start → one fight in a fixture encounter → session end) driving Claude with the skills; confirm every state change went through the engine, the summary/commit exist, and `git log` shows `session NNN start` and `session NNN: ...` boundary commits.

- [ ] **Step 4: Commit**

```bash
git add .claude
git commit -m "feat(claude): combat loop and session-end dreaming skills"
```

---

### Task 21: World instantiation skill + end-to-end test

**Files:**
- Create: `.claude/skills/world-new/SKILL.md`, `engine/tests/test_e2e.py`
- Modify: `README.md` (usage section)

**Interfaces:**
- Consumes: everything.
- Produces: the v1 milestone gate.

- [ ] **Step 1: Write the world-new skill**

`.claude/skills/world-new/SKILL.md`:

```markdown
---
name: world-new
description: Use when creating a new ky-ttrpg world (campaign) from a game definition.
---

# New world

1. Ask (if not given): game to use (default `games/reference`), world
   name, directory to create it in.
2. `engine world init <dir> --game <game-path> --name "<name>"`
3. `cd <dir> && git init && git add -A && git commit -m "world created: <name>"`
4. Tag the pristine state: `git tag genesis`.
5. Offer character creation: for each PC run
   `engine char create --name ... --class ... --race ... --assign ... --skills ...`
   (standard array 15,14,13,12,10,8; class skill lists come from the
   game's class files). Commit: `git commit -am "party created"`.
6. Remind the operator: sessions start with the gm-session skill;
   save points are `git tag`; forking a timeline is `git branch` from
   any tag or commit (branches never merge).
```

- [ ] **Step 2: Write the failing e2e test**

`engine/tests/test_e2e.py` — the whole v1 mechanical loop against the real reference game:

```python
import json

from typer.testing import CliRunner

from ttrpg_engine import worldfs
from ttrpg_engine.cli import app
from .test_reference_game import REFERENCE

runner = CliRunner()

PCS = [
    ("Borin", "fighter", "dwarf", "STR=15,CON=14,DEX=13,WIS=12,INT=10,CHA=8", "athletics,perception"),
    ("Brin", "rogue", "halfling", "DEX=15,WIS=14,INT=13,CON=12,STR=10,CHA=8", "stealth,perception,deception"),
    ("Mira", "cleric", "human", "WIS=15,CON=14,STR=13,DEX=12,INT=10,CHA=8", "insight,medicine"),
    ("Ezren", "wizard", "elf", "INT=15,DEX=14,CON=13,WIS=12,STR=10,CHA=8", "arcana,investigation"),
]


def run(args, expect_ok=True, seed=42):
    # vary the seed per call where outcomes must not repeat: a fixed seed
    # reseeds the RNG identically on every invocation
    res = runner.invoke(app, ["--seed", str(seed), *args])
    data = json.loads(res.stdout.strip().splitlines()[-1])
    if expect_ok:
        assert res.exit_code == 0, res.stdout
    return data


def test_full_adventure_loop(tmp_path, monkeypatch):
    root = tmp_path / "campaign"
    worldfs.init_world(root, REFERENCE, "E2E Campaign")
    monkeypatch.chdir(root)

    for name, cls, race, assign, skills in PCS:
        run(["char", "create", "--name", name, "--class", cls, "--race", race,
             "--assign", assign, "--skills", skills])
    run(["session", "start"])

    # town -> travel -> ambush
    run(["travel", "--to", "old-road"])
    start = run(["encounter", "start", "maps/encounters/road-ambush.yaml"])
    assert len(start["order"]) == 4 + 3

    # grind the ambush: the fighter whacks each monster until it drops.
    # the seed MUST vary per swing — a constant seed rolls the same d20
    # forever and a guaranteed-miss matchup would never terminate.
    enc = worldfs.read_yaml(root / "state" / "encounter.yaml")
    swing = 100
    for mid in list(enc["monsters"]):
        while True:
            enc = worldfs.read_yaml(root / "state" / "encounter.yaml")
            if enc["monsters"][mid]["dead"]:
                break
            swing += 1
            # teleport the fighter adjacent (GM force) and attack
            mx, my = enc["positions"][mid]
            run(["move", "--actor", "pc-borin", "--to", f"{max(0, mx-1)},{my}", "--force"],
                seed=swing)
            run(["attack", "--attacker", "pc-borin", "--target", mid],
                expect_ok=False, seed=swing)
    end = run(["encounter", "end"])
    assert end["xp_each"] > 0

    # rest, march to the dungeon, level check
    run(["rest", "--type", "long"])
    run(["travel", "--to", "barrow-woods"])
    run(["travel", "--to", "barrowdeep"])
    run(["xp", "grant", "--amount", "300", "--reason", "e2e shortcut"])
    lvl = run(["level", "up", "--actor", "pc-borin"])
    assert lvl["level"] == 2

    # boss room exists and renders
    run(["encounter", "start", "maps/encounters/kings-tomb.yaml"])
    render = run(["map", "render", "--svg"])
    assert (root / "renders" / "index.html").exists()
    assert "#" in render["map"] or "~" in render["map"]

    # audit trail exists and never contradicts state
    events = sorted((root / "timeline").glob("*.yaml"))
    assert len(events) > 10
    party = worldfs.read_yaml(root / "state" / "party.yaml")
    assert party["location"] == "barrowdeep"
```

Note the `expect_ok=False` on attacks: a miss still exits 0; only out-of-range/dead-target errors exit 1, and the loop's re-read tolerates both.

- [ ] **Step 3: Run it**

Run: `cd engine && uv run pytest tests/test_e2e.py -q`
Expected: PASS. Fix whatever it flushes out (this test exists to catch cross-module seams).

- [ ] **Step 4: Update README**

Add a "Playing" section to `README.md`: install (`uv tool install --editable ./engine`), create a world (world-new skill or `engine world init`), launch (`cd <world> && claude --agent gm`), and the three operator phrases ("GM override", "manual GM", "auto GM").

- [ ] **Step 5: Full suite + commit**

Run: `cd engine && uv run pytest -q`
Expected: all PASS.

```bash
git add engine .claude README.md
git commit -m "feat: world-new skill, e2e adventure test, playing docs"
```

---

## Post-v1 (explicitly deferred)

Fork management skill (git branch/tag ceremony), Insert mode + predestination validator, no-merge hook for world repos, region-map image generation, languages/alignment/crafting/weather/multiclassing. None of these block the v1 milestone; the design doc covers their intended shape.

## Execution notes

- Tasks 1–16 are strictly ordered (each consumes the previous interfaces). Tasks 17–18 (content) can run in parallel with 19–20 (skills) after 16; Task 21 needs everything.
- The v1 milestone is done when: `uv run pytest -q` is green, the Task 18 smoke script works, and one real playthrough (Task 20 step 3 / Task 21) has been run from `claude --agent gm`.




