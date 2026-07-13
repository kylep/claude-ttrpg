import json
import random
from pathlib import Path

import typer

from ttrpg_engine import chargen, checks, combat, dice, game as game_mod, render, timeline, worldfs
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


@app.command()
def move(actor: str = typer.Option(...), to: str = typer.Option(..., help="X,Y"),
         force: bool = typer.Option(False, "--force")):
    try:
        x, y = (int(v) for v in to.split(","))
    except ValueError:
        fail("bad_coord", f"--to must be X,Y, got {to!r}")
    emit(guard(combat.move, require_root(), actor, (x, y), force=force))
