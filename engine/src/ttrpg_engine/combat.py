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
