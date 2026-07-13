import re
from pathlib import Path

from ttrpg_engine import derive, timeline, worldfs
from ttrpg_engine.derive import attr_mod
from ttrpg_engine.errors import EngineError
from ttrpg_engine.game import ATTRS


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


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
    if (len(skills) != cls["skill_choices"] or len(set(skills)) != len(skills)
            or not set(skills) <= set(cls["skills"])):
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
        "ac": 0,
        "speed": race["speed"], "proficiency": prof, "skills": skills,
        "attacks": [],
        "spells_known": list(level1["spells"]),
        "spell_slots": {lvl: {"max": n, "current": n} for lvl, n in level1["slots"].items()},
        "features": list(level1["features"]),
        "inventory": [{"item": i, "qty": 1, "equipped": True} for i in cls["starting_gear"]],
        "gold": cls["starting_gold"], "effects": [],
    }
    derive.recompute(sheet, g)
    worldfs.write_yaml(worldfs.state(root, f"party/{pc_id}"), sheet)
    party = worldfs.read_yaml(worldfs.state(root, "party"))
    party["members"].append(pc_id)
    worldfs.write_yaml(worldfs.state(root, "party"), party)
    timeline.append_event(root, type_="character", actors=[pc_id],
                          summary=f"{name} the {race_name} {cls_name} joins the party")
    return sheet
