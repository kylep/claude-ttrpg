from pathlib import Path

from ttrpg_engine import worldfs
from ttrpg_engine.chargen import attr_mod
from ttrpg_engine.errors import EngineError


def run(root: Path, actor: str, attr: str, dc: int, *,
        skill: str | None, adv: bool, dis: bool, roll_fn) -> dict:
    sheet = worldfs.read_yaml(worldfs.state(root, f"party/{actor}"))
    if attr not in sheet["attributes"]:
        raise EngineError("unknown_attr", f"no attribute {attr!r} on {actor}")
    modifier = attr_mod(sheet["attributes"][attr])
    if skill and skill in sheet["skills"]:
        modifier += sheet["proficiency"]
    natural, total = roll_fn(modifier, adv, dis)
    crit = "hit" if natural == 20 else "fumble" if natural == 1 else None
    return {"actor": actor, "attr": attr, "skill": skill, "modifier": modifier,
            "natural": natural, "total": total, "dc": dc,
            "success": total >= dc, "crit": crit}
