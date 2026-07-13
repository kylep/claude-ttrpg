from pathlib import Path
from random import Random

from ttrpg_engine import derive, dice, timeline, worldfs
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
    derive.recompute(sheet, g)
    worldfs.write_yaml(worldfs.state(root, f"party/{actor}"), sheet)
    timeline.append_event(root, type_="level", actors=[actor],
                          summary=f"{actor} reaches level {new_level} (+{gain} hp)")
    return {"actor": actor, "level": new_level, "hp_gain": gain,
            "features": sheet["features"], "spells_known": sheet["spells_known"]}
