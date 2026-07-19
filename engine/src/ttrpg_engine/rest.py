from pathlib import Path
from random import Random

from ttrpg_engine import clock as clock_mod
from ttrpg_engine import derive, timeline, worldfs
from ttrpg_engine.errors import EngineError


def take(root: Path, g: dict, kind: str, rng: Random, pcs: list[str] | None = None) -> dict:
    """Rest the party (or `pcs`), advancing the clock. A short rest heals one
    hit die and clears unconscious/dying once above 0 hp; a long rest restores
    full hp and all spell slots and resets effects to equipment-granted ones.
    The dead are skipped."""
    if kind not in ("short", "long"):
        raise EngineError("bad_rest", "type must be short or long")
    if (root / "state" / "encounter.yaml").exists():
        raise EngineError("encounter_active", "cannot rest mid-encounter")
    hours = g["recovery"][f"{kind}_rest"]["hours"]
    party = worldfs.read_yaml(worldfs.state(root, "party"))
    if pcs is None:
        targets = list(party["members"])
    else:
        for pid in pcs:
            if pid not in party["members"]:
                raise EngineError("not_found", f"no such PC {pid}")
        targets = pcs
    healed = {}
    for pc_id in targets:
        sheet = worldfs.read_yaml(worldfs.state(root, f"party/{pc_id}"))
        if derive.is_dead(sheet):
            continue
        before = sheet["hp"]
        if kind == "short":
            gain = derive.hit_die_gain(g["classes"][sheet["class"]]["hit_die"],
                                       sheet["attributes"]["CON"], rng)
            sheet["hp"] = min(sheet["max_hp"], sheet["hp"] + gain)
            if sheet["hp"] > 0:
                sheet["effects"] = [e for e in sheet["effects"]
                                    if e["name"] not in ("unconscious", "dying")]
                sheet.pop("death_saves", None)
        else:
            sheet["hp"] = sheet["max_hp"]
            for slot in sheet["spell_slots"].values():
                slot["current"] = slot["max"]
            sheet["effects"] = derive.equipment_effects(sheet, g)
            sheet.pop("death_saves", None)
            sheet["wounds"] = []          # a full night's rest mends narrative wounds
        healed[pc_id] = [before, sheet["hp"]]
        worldfs.write_yaml(worldfs.state(root, f"party/{pc_id}"), sheet)
    clk = clock_mod.advance(worldfs.read_yaml(worldfs.state(root, "clock")), hours)
    worldfs.write_yaml(worldfs.state(root, "clock"), clk)
    timeline.append_event(root, type_="rest", actors=list(healed),
                          summary=f"the party takes a {kind} rest ({hours}h)",
                          delta={p: {"hp": hp} for p, hp in healed.items()})
    return {"type": kind, "hours": hours, "healed": healed, "clock": clk}
