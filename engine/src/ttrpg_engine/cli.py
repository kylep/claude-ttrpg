import json
import random
from pathlib import Path

import typer

from ttrpg_engine import chargen, checks, combat, dice, export as export_mod, game as game_mod, inventory, level as level_mod, quests as quests_mod, render, rest as rest_mod, spells, timeline, travel as travel_mod, worldfs
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


def split_pcs(pcs: str | None) -> list[str] | None:
    """Parse a comma-separated --pcs option into a list, or None if omitted."""
    return [p.strip() for p in pcs.split(",") if p.strip()] if pcs else None


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
def encounter_start(map_rel: str, pcs: str | None = typer.Option(None, "--pcs", help="comma-separated PC ids")):
    root = require_root()
    g = guard(worldfs.load_game_for, root)
    emit(guard(combat.start, root, g, map_rel, rng, split_pcs(pcs)))


@enc_app.command("next")
def encounter_next():
    emit(guard(combat.next_turn, require_root(), rng))


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
    emit(guard(combat.apply_damage, require_root(), target, amount, source, rng))


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
    emit(guard(combat.remove_effect, require_root(), target, name, rng))


@app.command()
def deathsave(actor: str = typer.Option(...)):
    emit(guard(combat.death_save, require_root(), actor, roll_fn=d20_roll))


@app.command()
def cast(caster: str = typer.Option(...), spell: str = typer.Option(...),
         target: str | None = typer.Option(None),
         at: str | None = typer.Option(None, "--at", help="X,Y cell for area spells")):
    root = require_root()
    g = guard(worldfs.load_game_for, root)
    cell = None
    if at is not None:
        try:
            x, y = (int(v) for v in at.split(","))
        except ValueError:
            fail("bad_coord", f"--at must be X,Y, got {at!r}")
        cell = (x, y)
    emit(guard(spells.cast, root, g, caster, spell, target, roll_fn=d20_roll, rng=rng, at=cell))


@app.command()
def ascend(actor: str = typer.Option(...)):
    emit(guard(combat.ascend, require_root(), actor))


@app.command()
def land(actor: str = typer.Option(...)):
    emit(guard(combat.land, require_root(), actor))


@app.command()
def fall(actor: str = typer.Option(...),
         dice_expr: str = typer.Option("2d6", "--dice", help="Fall damage roll.")):
    emit(guard(combat.fall, require_root(), actor, rng, dice_expr))


@app.command()
def hide(actor: str = typer.Option(...)):
    root = require_root()
    g = guard(worldfs.load_game_for, root)
    emit(guard(combat.hide, root, g, actor, roll_fn=d20_roll))


@app.command()
def stand(actor: str = typer.Option(...)):
    emit(guard(combat.stand, require_root(), actor))


@app.command()
def grapple(actor: str = typer.Option(...), target: str = typer.Option(...),
            release: bool = typer.Option(False, "--release")):
    emit(guard(combat.grapple, require_root(), actor, target,
               roll_fn=d20_roll, release=release))


@app.command()
def escape(actor: str = typer.Option(...)):
    emit(guard(combat.escape, require_root(), actor, roll_fn=d20_roll))


@app.command()
def shove(actor: str = typer.Option(...), target: str = typer.Option(...)):
    emit(guard(combat.shove, require_root(), actor, target, roll_fn=d20_roll))


@app.command()
def sight(actor: str = typer.Option(...), target: str = typer.Option(...)):
    emit(guard(combat.sight, require_root(), actor, target))


@app.command()
def rest(type_: str = typer.Option(..., "--type"),
         pcs: str | None = typer.Option(None, "--pcs", help="comma-separated PC ids")):
    root = require_root()
    g = guard(worldfs.load_game_for, root)
    emit(guard(rest_mod.take, root, g, type_, rng, split_pcs(pcs)))


@app.command()
def move(actor: str = typer.Option(...), to: str = typer.Option(..., help="X,Y"),
         force: bool = typer.Option(False, "--force")):
    try:
        x, y = (int(v) for v in to.split(","))
    except ValueError:
        fail("bad_coord", f"--to must be X,Y, got {to!r}")
    emit(guard(combat.move, require_root(), actor, (x, y), force=force))


@app.command()
def travel(to: str = typer.Option(...),
           pcs: str | None = typer.Option(None, "--pcs", help="comma-separated PC ids")):
    emit(guard(travel_mod.go, require_root(), to, split_pcs(pcs)))


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


@item_app.command("dispel")
def item_dispel(actor: str = typer.Option(...), item: str = typer.Option(...)):
    root = require_root()
    g = guard(worldfs.load_game_for, root)
    emit(guard(inventory.dispel, root, g, actor, item))


@app.command()
def equip(actor: str = typer.Option(...), item: str = typer.Option(...),
          force: bool = typer.Option(False, "--force")):
    root = require_root()
    g = guard(worldfs.load_game_for, root)
    emit(guard(inventory.equip, root, g, actor, item, force=force))


@app.command()
def unequip(actor: str = typer.Option(...), item: str = typer.Option(...),
            force: bool = typer.Option(False, "--force")):
    root = require_root()
    g = guard(worldfs.load_game_for, root)
    emit(guard(inventory.unequip, root, g, actor, item, force=force))


def _gold_target(actor: str | None, party: bool) -> str:
    if party == (actor is not None):
        fail("bad_target", "pass exactly one of --actor or --party")
    return "party" if party else actor


@gold_app.command("add")
def gold_add(amount: int = typer.Option(...), actor: str | None = typer.Option(None),
             party: bool = typer.Option(False, "--party")):
    if amount < 1:
        fail("bad_amount", f"amount must be >= 1, got {amount}")
    emit(guard(inventory.adjust_gold, require_root(), _gold_target(actor, party), amount))


@gold_app.command("spend")
def gold_spend(amount: int = typer.Option(...), actor: str | None = typer.Option(None),
               party: bool = typer.Option(False, "--party")):
    if amount < 1:
        fail("bad_amount", f"amount must be >= 1, got {amount}")
    emit(guard(inventory.adjust_gold, require_root(), _gold_target(actor, party), -amount))


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


quest_app = typer.Typer()
app.add_typer(quest_app, name="quest")


@quest_app.command("offer")
def quest_offer(
    title: str = typer.Option(...),
    desc: str = typer.Option(..., "--desc"),
    giver: str = typer.Option(..., help="npc:ID, pc:ID, or world"),
    gold: int = typer.Option(0),
    items: str | None = typer.Option(None, help="comma-separated"),
    xp: int = typer.Option(0),
    deadline: str | None = typer.Option(None, help="YYYY-MM-DD; omit for indefinite"),
    deadline_hour: int = typer.Option(9, "--deadline-hour"),
    spawn: bool = typer.Option(False, "--spawn", help="world only: reward materializes on completion"),
    escrow_from: str | None = typer.Option(None, "--escrow-from", help="npc:ID or pc:ID (world giver only)"),
):
    root = require_root()
    g = guard(worldfs.load_game_for, root)
    giver_type, giver_id = guard(quests_mod.parse_ref, giver)
    escrow_type = escrow_id = None
    if escrow_from:
        escrow_type, escrow_id = guard(quests_mod.parse_ref, escrow_from, allow_world=False)
    item_list = [i.strip() for i in items.split(",") if i.strip()] if items else []
    deadline_spec = {"date": deadline, "hour": deadline_hour} if deadline else None
    emit(guard(quests_mod.offer, root, g, title=title, description=desc,
               giver_type=giver_type, giver_id=giver_id, gold=gold, items=item_list,
               xp=xp, deadline=deadline_spec, spawn=spawn,
               escrow_from_type=escrow_type, escrow_from_id=escrow_id))


@quest_app.command("accept")
def quest_accept(quest_id: str, pcs: str = typer.Option(..., "--pcs", help="comma-separated PC ids")):
    root = require_root()
    emit(guard(quests_mod.accept, root, quest_id, split_pcs(pcs)))


@quest_app.command("complete")
def quest_complete(quest_id: str,
                   to: str | None = typer.Option(None, "--to", help="comma-separated PC ids; default accepted_by")):
    root = require_root()
    emit(guard(quests_mod.complete, root, quest_id, split_pcs(to)))


@quest_app.command("cancel")
def quest_cancel(quest_id: str):
    emit(guard(quests_mod.cancel, require_root(), quest_id))


@quest_app.command("list")
def quest_list(status: str | None = typer.Option(None, "--status")):
    """List quests. Side effect: any offered/accepted quest whose deadline
    has passed is transitioned to expired (escrow refunded) before listing."""
    root = require_root()
    emit({"quests": guard(quests_mod.list_quests, root, status)})


export_app = typer.Typer()
app.add_typer(export_app, name="export")

_EXPORT_FILENAMES = {
    "game": "claude-ttrpg-game-handbook.html",
    "world": "claude-ttrpg-world-guide.html",
    "campaign": "claude-ttrpg-campaign-book.html",
}
_EXPORT_RENDERERS = {
    "game": export_mod.render_game,
    "world": export_mod.render_world,
    "campaign": export_mod.render_campaign,
}


def _run_export(kind: str, out: Path, game: Path | None) -> None:
    root = None if game is not None else require_root()
    src = guard(export_mod.resolve_source, root, game)
    html_str, sections = guard(_EXPORT_RENDERERS[kind], src)
    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = (out_dir / _EXPORT_FILENAMES[kind]).resolve()
    path.write_text(html_str)
    emit({"file": str(path), "sections": sections})


@export_app.command("game")
def export_game_cmd(
    out: Path = typer.Option(Path("exports"), "--out", help="Output directory."),
    game: Path | None = typer.Option(None, "--game", help="Game repo path (repo-side, no world needed)."),
):
    _run_export("game", out, game)


@export_app.command("world")
def export_world_cmd(
    out: Path = typer.Option(Path("exports"), "--out", help="Output directory."),
    game: Path | None = typer.Option(None, "--game", help="Game repo path (repo-side, no world needed)."),
):
    _run_export("world", out, game)


@export_app.command("campaign")
def export_campaign_cmd(
    out: Path = typer.Option(Path("exports"), "--out", help="Output directory."),
    game: Path | None = typer.Option(None, "--game", help="Game repo path (repo-side, no world needed)."),
):
    _run_export("campaign", out, game)
