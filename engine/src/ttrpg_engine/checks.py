from pathlib import Path

from ttrpg_engine import combat, worldfs
from ttrpg_engine.chargen import attr_mod
from ttrpg_engine.errors import EngineError
from ttrpg_engine.render import load_encounter


def run(root: Path, actor: str, attr: str, dc: int, *,
        skill: str | None, adv: bool, dis: bool, roll_fn) -> dict:
    """Roll an attribute check for `actor` against `dc`. Adds proficiency when
    `skill` is one the PC has; applies disadvantage from active conditions on
    top of the passed `dis`; flags crit/fumble on a natural roll at the
    ruleset's bounds."""
    sheet = worldfs.read_yaml(worldfs.state(root, f"party/{actor}"))
    if attr not in sheet["attributes"]:
        raise EngineError("unknown_attr", f"no attribute {attr!r} on {actor}")
    modifier = attr_mod(sheet["attributes"][attr])
    if skill and skill in sheet["skills"]:
        modifier += sheet["proficiency"]
    enc = load_encounter(root) if (root / "state" / "encounter.yaml").exists() else None
    dis_from = combat.self_dis_conditions(root, enc, actor, sheet)
    natural, total = roll_fn(modifier, adv, dis or bool(dis_from))
    crit_on, fumble_on = combat.crit_bounds(worldfs.load_game_for(root))
    crit = "hit" if natural == crit_on else "fumble" if natural == fumble_on else None
    result = {"actor": actor, "attr": attr, "skill": skill, "modifier": modifier,
              "natural": natural, "total": total, "dc": dc,
              "success": total >= dc, "crit": crit}
    if dis_from:
        result["dis_from"] = dis_from
    return result
