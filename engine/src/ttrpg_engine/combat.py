from pathlib import Path
from random import Random

from ttrpg_engine import dice, grid, timeline, worldfs
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


def resolve_actor(root: Path, cid: str):
    enc = None
    if (root / "state" / "encounter.yaml").exists():
        enc = load_encounter(root)
    if enc and cid in enc["monsters"]:
        return "monster", enc["monsters"][cid], enc
    path = worldfs.state(root, f"party/{cid}")
    if path.exists():
        return "pc", worldfs.read_yaml(path), enc
    raise EngineError("not_found", f"no combatant {cid}")


def _persist(root, kind, data, enc):
    if kind == "pc":
        save_pc(root, data)
        if enc is not None:
            save_encounter(root, enc)
    else:
        save_encounter(root, enc)


def apply_damage(root: Path, target: str, amount: int, source: str) -> dict:
    kind, data, enc = resolve_actor(root, target)
    before = data["hp"]
    data["hp"] = max(0, before - amount)
    dropped = data["hp"] == 0 and before > 0
    if dropped:
        if kind == "monster":
            data["dead"] = True
        else:
            names = {e["name"] for e in data["effects"]}
            data["effects"] += [{"name": n, "duration": -1}
                                for n in ("unconscious", "dying") if n not in names]
            data["death_saves"] = {"successes": 0, "fails": 0}
    _persist(root, kind, data, enc)
    timeline.append_event(root, type_="damage", actors=[target],
                          summary=f"{target} takes {amount} damage ({source})",
                          delta={target: {"hp": [before, data["hp"]]}})
    return {"target": target, "amount": amount, "hp": [before, data["hp"]],
            "dropped": dropped}


def apply_heal(root: Path, target: str, amount: int, source: str) -> dict:
    kind, data, enc = resolve_actor(root, target)
    before = data["hp"]
    data["hp"] = min(data["max_hp"], before + amount)
    if kind == "pc" and data["hp"] > 0:
        data["effects"] = [e for e in data["effects"]
                           if e["name"] not in ("unconscious", "dying")]
        data.pop("death_saves", None)
    _persist(root, kind, data, enc)
    timeline.append_event(root, type_="heal", actors=[target],
                          summary=f"{target} heals {amount} ({source})",
                          delta={target: {"hp": [before, data["hp"]]}})
    return {"target": target, "amount": amount, "hp": [before, data["hp"]]}


def attack(root: Path, attacker: str, target: str, *, attack_name: str | None,
           adv: bool, dis: bool, roll_fn, rng: Random) -> dict:
    _, a_data, enc = resolve_actor(root, attacker)
    _, t_data, _ = resolve_actor(root, target)
    attacks = a_data["attacks"]
    atk = next((a for a in attacks if a["name"] == attack_name), attacks[0] if attacks else None)
    if atk is None:
        raise EngineError("no_attack", f"{attacker} has no attack {attack_name!r}")
    if enc and attacker in enc["positions"] and target in enc["positions"]:
        dist = grid.chebyshev(tuple(enc["positions"][attacker]),
                              tuple(enc["positions"][target]))
        if dist > atk.get("range", 1):
            raise EngineError("out_of_range",
                              f"{target} is {dist} away, range is {atk.get('range', 1)}")
    natural, total = roll_fn(atk["attack_mod"], adv, dis)
    crit = "hit" if natural == 20 else "fumble" if natural == 1 else None
    hit = natural != 1 and (natural == 20 or total >= t_data["ac"])
    damage = 0
    if hit:
        dmg = dice.roll(str(atk["damage"]), rng)
        damage = dmg.total
        if crit == "hit":
            damage += sum(dice.roll(str(atk["damage"]), rng).rolls)  # dice again, modifier once
    result = {"attacker": attacker, "target": target, "attack": atk["name"],
              "natural": natural, "total": total, "vs_ac": t_data["ac"],
              "hit": hit, "crit": crit, "damage": damage}
    verb = "hits" if hit else "misses"
    timeline.append_event(root, type_="attack", actors=[attacker, target],
                          summary=f"{attacker} {verb} {target} with {atk['name']}"
                                  + (f" for {damage}" if hit else ""))
    if hit and damage:
        dmg_result = apply_damage(root, target, damage, source=f"{attacker}:{atk['name']}")
        result["target_hp"] = dmg_result["hp"]
        result["dropped"] = dmg_result["dropped"]
    return result


def set_effect(root: Path, target: str, name: str, duration: int) -> dict:
    kind, data, enc = resolve_actor(root, target)
    data["effects"] = [e for e in data["effects"] if e["name"] != name]
    data["effects"].append({"name": name, "duration": duration})
    _persist(root, kind, data, enc)
    timeline.append_event(root, type_="effect", actors=[target],
                          summary=f"{target} gains {name} ({duration} rounds)")
    return {"target": target, "effects": data["effects"]}


def remove_effect(root: Path, target: str, name: str) -> dict:
    kind, data, enc = resolve_actor(root, target)
    data["effects"] = [e for e in data["effects"] if e["name"] != name]
    _persist(root, kind, data, enc)
    timeline.append_event(root, type_="effect", actors=[target],
                          summary=f"{target} loses {name}")
    return {"target": target, "effects": data["effects"]}


def death_save(root: Path, actor: str, *, roll_fn) -> dict:
    kind, sheet, enc = resolve_actor(root, actor)
    if kind != "pc" or "dying" not in {e["name"] for e in sheet["effects"]}:
        raise EngineError("not_dying", f"{actor} is not dying")
    natural, _ = roll_fn(0, False, False)
    saves = sheet.setdefault("death_saves", {"successes": 0, "fails": 0})
    if natural == 20:
        result = "revived"
    elif natural >= 10:
        saves["successes"] += 1
        result = "stable" if saves["successes"] >= 3 else "success"
    else:
        saves["fails"] += 1
        result = "dead" if saves["fails"] >= 3 else "fail"
    if result == "revived":
        sheet["hp"] = 1
        sheet["effects"] = [e for e in sheet["effects"]
                            if e["name"] not in ("unconscious", "dying")]
        sheet.pop("death_saves", None)
    elif result == "stable":
        sheet["effects"] = [e for e in sheet["effects"] if e["name"] != "dying"]
        sheet.pop("death_saves", None)
    elif result == "dead":
        sheet["effects"].append({"name": "dead", "duration": -1})
    _persist(root, kind, sheet, enc)
    timeline.append_event(root, type_="deathsave", actors=[actor],
                          summary=f"{actor} death save: {natural} -> {result}")
    if result == "dead":
        timeline.append_event(root, type_="death", actors=[actor],
                              summary=f"{actor} has died")
    return {"actor": actor, "natural": natural, "result": result,
            "saves": sheet.get("death_saves")}
