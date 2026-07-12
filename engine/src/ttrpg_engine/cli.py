import json
import random
from pathlib import Path

import typer

from ttrpg_engine import dice, game as game_mod, worldfs
from ttrpg_engine.errors import EngineError

app = typer.Typer(add_completion=False, no_args_is_help=True)
rng = random.Random()

_world_override: Path | None = None


@app.callback()
def _root(
    seed: int | None = typer.Option(None, "--seed", help="Seed the RNG (testing)."),
    world: Path | None = typer.Option(None, "--world", help="World repo path (default: discover from cwd)."),
):
    global _world_override
    if seed is not None:
        rng.seed(seed)
    _world_override = world


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


def require_root() -> Path:
    return guard(worldfs.find_root, _world_override)


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


world_app = typer.Typer()
state_app = typer.Typer()
app.add_typer(world_app, name="world")
app.add_typer(state_app, name="state")


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
