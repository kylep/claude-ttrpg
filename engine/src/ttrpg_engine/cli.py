import json
import random
import re
import sys
from pathlib import Path

import typer

from ttrpg_engine import chargen, checks, combat, dice, export as export_mod, game as game_mod, inventory, level as level_mod, quests as quests_mod, render, rest as rest_mod, serve as serve_mod, spells, story_log, timeline, travel as travel_mod, worldfs
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
    """Emit a JSON error payload and exit non-zero; never returns."""
    typer.echo(json.dumps({"error": {"code": code, "message": message}}))
    raise typer.Exit(1)


def split_csv(s: str | None) -> list[str]:
    """Split a comma-separated option into trimmed, non-empty parts."""
    return [p.strip() for p in s.split(",") if p.strip()] if s else []


def split_pcs(pcs: str | None) -> list[str] | None:
    """Parse a comma-separated --pcs option into a list, or None if omitted
    (None means 'the whole party', distinct from an empty subset)."""
    return split_csv(pcs) or None


def parse_xy(spec: str, option: str) -> tuple[int, int]:
    """Parse an 'X,Y' cell option into a coordinate tuple."""
    try:
        x, y = (int(v) for v in spec.split(","))
    except ValueError:
        raise EngineError("bad_coord", f"{option} must be X,Y, got {spec!r}")
    return x, y


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


def require_root_and_game() -> tuple[Path, dict]:
    """The world root plus its loaded game — the pair almost every stateful
    command needs."""
    root = require_root()
    return root, guard(worldfs.load_game_for, root)


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


@world_app.command("upgrade")
def world_upgrade(
    check: bool = typer.Option(False, "--check", help="Report kit status only; change nothing."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would change without writing."),
    force: bool = typer.Option(False, "--force", help="Also overwrite settings.json."),
):
    """Re-sync this world's GM agent + skills with the engine's current kit.

    The world is a git repo, so review the diff and commit — the upgrade is
    a save point. `--check` just reports whether the world is behind.
    """
    root = require_root()
    if check:
        emit(guard(worldfs.check_kit, root))
    else:
        emit(guard(worldfs.upgrade_agent_kit, root, dry_run=dry_run, force=force))


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
    story_log.post(root, "system", md=f"**Session {sess['current']}** begins.")
    emit({"session": sess["current"]})


@override_app.command("log")
def override_log(summary: str = typer.Option(...), actors: str = typer.Option("", help="comma-separated ids")):
    root = require_root()
    event = timeline.append_event(root, type_="override", summary=summary,
                                  actors=split_csv(actors), override=True)
    emit({"event": event})


story_app = typer.Typer()
app.add_typer(story_app, name="story")


def _story_text(text: str) -> str:
    """'-' reads the prose from stdin (heredoc-friendly for long beats)."""
    if text == "-":
        text = sys.stdin.read()
    text = text.strip()
    if not text:
        raise EngineError("empty_text", "no text given")
    return text


@story_app.command("narrate")
def story_narrate(text: str = typer.Option(..., help="markdown prose; '-' reads stdin")):
    """Post table-facing narration to the story log (the live viewer's feed)."""
    root = require_root()
    emit(guard(story_log.post, root, "narration", md=guard(_story_text, text)))


@story_app.command("scene")
def story_scene(title: str = typer.Option(...),
                subtitle: str = typer.Option("", help="e.g. a styled date/time line")):
    """Post a scene header — location and moment, as the table should read them."""
    root = require_root()
    emit(guard(story_log.post, root, "scene", title=title, subtitle=subtitle))


@story_app.command("choices")
def story_choices(item: list[str] = typer.Option(..., "--item", help="one option, markdown; repeatable"),
                  title: str = typer.Option("What you can do right now")):
    """Post the current action menu — what the players can do from here."""
    root = require_root()
    emit(guard(story_log.post, root, "choices", title=title, items=list(item)))


@story_app.command("action")
def story_action(pc: str = typer.Option(...), text: str = typer.Option(..., help="'-' reads stdin")):
    """Post a player's in-character line, attributed to their PC."""
    root = require_root()
    sheet = guard(worldfs.read_yaml, worldfs.state(root, f"party/{pc}"))
    emit(guard(story_log.post, root, "action", pc=pc, name=sheet["name"],
               md=guard(_story_text, text)))


@story_app.command("reveal")
def story_reveal(npc: str = typer.Option(None, help="id from canon/npcs.yaml"),
                 monster: str = typer.Option(None, help="bestiary type id"),
                 pc: str = typer.Option(None, help="pc id")):
    """Drop an entity card into the feed when someone is introduced at the table."""
    root = require_root()
    if sum(x is not None for x in (npc, monster, pc)) != 1:
        fail("bad_reveal", "pass exactly one of --npc / --monster / --pc")
    if npc:
        npcs = guard(worldfs.read_yaml, root / "canon" / "npcs.yaml")
        if npc not in npcs:
            fail("not_found", f"no NPC {npc!r} in canon/npcs.yaml")
        emit(guard(story_log.post, root, "npc", ref=npc, name=npcs[npc].get("name", npc)))
    elif monster:
        g = guard(worldfs.load_game_for, root)
        entry = guard(game_mod.bestiary_entry, g, monster)
        emit(guard(story_log.post, root, "monster", ref=monster,
                   name=entry.get("name", monster)))
    else:
        sheet = guard(worldfs.read_yaml, worldfs.state(root, f"party/{pc}"))
        emit(guard(story_log.post, root, "character", ref=pc, name=sheet["name"]))


char_app = typer.Typer()
app.add_typer(char_app, name="char")


def parse_kv_ints(spec: str) -> dict[str, int]:
    """Parse 'STR=10,DEX=15' into {attr: int}, upper-casing keys.

    Raises bad_assign on any pair whose value isn't an integer."""
    out = {}
    for pair in spec.split(","):
        k, _, v = pair.partition("=")
        if not re.fullmatch(r"-?\d+", v.strip()):
            raise EngineError("bad_assign", f"bad assignment {pair!r}")
        out[k.strip().upper()] = int(v)
    return out


@char_app.command("options")
def char_options():
    """Character-creation options for the world's game (standard array, races,
    classes with skill counts and recommended defaults) as JSON — the menu a
    party-creation wizard presents. Read-only."""
    root, g = require_root_and_game()
    emit(chargen.options(g))


@char_app.command("create")
def char_create(
    name: str = typer.Option(...),
    cls: str = typer.Option(..., "--class"),
    race: str = typer.Option(...),
    assign: str = typer.Option(..., help="e.g. DEX=15,WIS=14,INT=13,CON=12,STR=10,CHA=8"),
    skills: str = typer.Option(..., help="comma-separated"),
    played_by: str = typer.Option(None, "--played-by",
                                  help="who runs this PC at the table (a player's name, or GM)"),
):
    root, g = require_root_and_game()
    sheet = guard(chargen.create, root, g, name=name, cls_name=cls, race_name=race,
                  assign=guard(parse_kv_ints, assign),
                  skills=[s.strip() for s in skills.split(",")],
                  played_by=played_by)
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
    root, g = require_root_and_game()
    emit(guard(combat.start, root, g, map_rel, rng, split_pcs(pcs)))


@enc_app.command("next")
def encounter_next():
    emit(guard(combat.next_turn, require_root(), rng))


@enc_app.command("end")
def encounter_end():
    root, g = require_root_and_game()
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
               duration: int = typer.Option(-1),
               source: str | None = typer.Option(None, help="Combatant causing it (frightened uses this).")):
    emit(guard(combat.set_effect, require_root(), target, name, duration, source))


@effect_app.command("remove")
def effect_remove(target: str = typer.Option(...), name: str = typer.Option(...)):
    emit(guard(combat.remove_effect, require_root(), target, name, rng))


@app.command()
def deathsave(actor: str = typer.Option(...)):
    emit(guard(combat.death_save, require_root(), actor, roll_fn=d20_roll))


@app.command()
def revive(actor: str = typer.Option(...),
           hp: int = typer.Option(1, help="HP to return at (default 1).")):
    """Restore a dead PC to life (the GM decides the fiction and any cost)."""
    emit(guard(combat.revive, require_root(), actor, hp=hp))


@app.command()
def cast(caster: str = typer.Option(...), spell: str = typer.Option(...),
         target: str | None = typer.Option(None),
         at: str | None = typer.Option(None, "--at", help="X,Y cell for area spells")):
    root, g = require_root_and_game()
    cell = guard(parse_xy, at, "--at") if at is not None else None
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
    root, g = require_root_and_game()
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
    root, g = require_root_and_game()
    emit(guard(rest_mod.take, root, g, type_, rng, split_pcs(pcs)))


@app.command()
def move(actor: str = typer.Option(...), to: str = typer.Option(..., help="X,Y"),
         force: bool = typer.Option(False, "--force")):
    cell = guard(parse_xy, to, "--to")
    emit(guard(combat.move, require_root(), actor, cell, force=force))


@app.command()
def serve(port: int = typer.Option(8787, help="Port on 127.0.0.1.")):
    """Serve the live world viewer (player lens at /, GM lens at /gm)."""
    root = require_root()
    server = guard(serve_mod.run, root, port)
    emit({"player": f"http://127.0.0.1:{port}/",
          "gm": f"http://127.0.0.1:{port}/gm", "world": str(root)})
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


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
    root, g = require_root_and_game()
    emit(guard(inventory.add_item, root, g, actor, item, qty))


@item_app.command("remove")
def item_remove(actor: str = typer.Option(...), item: str = typer.Option(...),
                qty: int = typer.Option(1)):
    root, g = require_root_and_game()
    emit(guard(inventory.remove_item, root, g, actor, item, qty))


@item_app.command("use")
def item_use(actor: str = typer.Option(...), item: str = typer.Option(...),
             target: str | None = typer.Option(None, help="Defaults to the actor."),
             force: bool = typer.Option(False, "--force")):
    root, g = require_root_and_game()
    emit(guard(inventory.use, root, g, actor, item, target, rng, force=force))


@item_app.command("dispel")
def item_dispel(actor: str = typer.Option(...), item: str = typer.Option(...)):
    root, g = require_root_and_game()
    emit(guard(inventory.dispel, root, g, actor, item))


@app.command()
def equip(actor: str = typer.Option(...), item: str = typer.Option(...),
          force: bool = typer.Option(False, "--force")):
    root, g = require_root_and_game()
    emit(guard(inventory.equip, root, g, actor, item, force=force))


@app.command()
def unequip(actor: str = typer.Option(...), item: str = typer.Option(...),
            force: bool = typer.Option(False, "--force")):
    root, g = require_root_and_game()
    emit(guard(inventory.unequip, root, g, actor, item, force=force))


def _gold_target(actor: str | None, party: bool) -> str:
    """Resolve the gold target id, requiring exactly one of --actor/--party
    (the equality check rejects both set and both omitted)."""
    if party == (actor is not None):
        fail("bad_target", "pass exactly one of --actor or --party")
    return "party" if party else actor


@gold_app.command("add")
def gold_add(amount: int = typer.Option(...), actor: str | None = typer.Option(None),
             party: bool = typer.Option(False, "--party"),
             reason: str = typer.Option("", help="why — lands in the timeline record")):
    if amount < 1:
        fail("bad_amount", f"amount must be >= 1, got {amount}")
    emit(guard(inventory.adjust_gold, require_root(), _gold_target(actor, party), amount,
               reason))


@gold_app.command("spend")
def gold_spend(amount: int = typer.Option(...), actor: str | None = typer.Option(None),
               party: bool = typer.Option(False, "--party"),
               reason: str = typer.Option("", help="why — lands in the timeline record")):
    if amount < 1:
        fail("bad_amount", f"amount must be >= 1, got {amount}")
    emit(guard(inventory.adjust_gold, require_root(), _gold_target(actor, party), -amount,
               reason))


xp_app = typer.Typer()
level_app = typer.Typer()
app.add_typer(xp_app, name="xp")
app.add_typer(level_app, name="level")


@xp_app.command("grant")
def xp_grant(amount: int = typer.Option(...), reason: str = typer.Option("")):
    emit(guard(level_mod.grant_xp, require_root(), amount, reason))


@level_app.command("up")
def level_up(actor: str = typer.Option(...)):
    root, g = require_root_and_game()
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
    root, g = require_root_and_game()
    giver_type, giver_id = guard(quests_mod.parse_ref, giver)
    escrow_type = escrow_id = None
    if escrow_from:
        escrow_type, escrow_id = guard(quests_mod.parse_ref, escrow_from, allow_world=False)
    if not 0 <= deadline_hour <= 23:
        fail("bad_hour", f"--deadline-hour must be 0–23, got {deadline_hour}")
    deadline_spec = {"date": deadline, "hour": deadline_hour} if deadline else None
    emit(guard(quests_mod.offer, root, g, title=title, description=desc,
               giver_type=giver_type, giver_id=giver_id, gold=gold, items=split_csv(items),
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
