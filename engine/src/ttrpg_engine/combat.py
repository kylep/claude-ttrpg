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


def attack_kind(atk: dict) -> str:
    """melee|ranged for an attack. Explicit atk['kind'] wins; otherwise
    melee if range <= 1, else ranged."""
    kind = atk.get("kind")
    if kind in ("melee", "ranged"):
        return kind
    return "melee" if atk.get("range", 1) <= 1 else "ranged"


def effect_names(data: dict) -> set[str]:
    return {e["name"] for e in data.get("effects", [])}


def skill_mod(data: dict, attr: str, skill: str) -> int:
    """Attribute modifier, plus proficiency if the combatant has the skill.
    Monsters have no skills/proficiency keys and fall back to the bare mod."""
    mod = attr_mod(data["attributes"][attr])
    if skill in data.get("skills", []):
        mod += data.get("proficiency", 0)
    return mod


def passive_perception(data: dict) -> int:
    return 10 + skill_mod(data, "WIS", "perception")


def in_darkness(enc: dict | None, cid: str, data: dict) -> bool:
    """True when cid stands in an unlit cell and carries no light of its own."""
    if enc is None or cid not in enc["positions"]:
        return False
    return (grid.is_dark(enc, enc["positions"][cid])
            and "lit" not in effect_names(data))


def _frightened_active(root: Path, enc: dict | None, cid: str, data: dict) -> bool:
    """Frightened bites while the recorded fear source is alive and in view;
    a sourceless frightened effect always bites."""
    entry = next((e for e in data.get("effects", []) if e["name"] == "frightened"), None)
    if entry is None:
        return False
    src = entry.get("source")
    if not src:
        return True
    if enc is None or src not in enc["positions"] or cid not in enc["positions"]:
        return False
    if not is_living(root, enc, src):
        return False
    return grid.line_of_sight(enc, tuple(enc["positions"][cid]),
                              tuple(enc["positions"][src]))


def self_dis_conditions(root: Path, enc: dict | None, cid: str, data: dict) -> list[str]:
    """Conditions that put a combatant's own d20 rolls (attacks, checks,
    contests, hiding) at disadvantage."""
    out = []
    if "poisoned" in effect_names(data):
        out.append("poisoned")
    if _frightened_active(root, enc, cid, data):
        out.append("frightened")
    return out


def roll_conditions(a_eff: set[str], t_eff: set[str], kind: str) -> tuple[list[str], list[str]]:
    """Advantage/disadvantage sources an attack roll picks up from the
    engine-enforced conditions on attacker (a_eff) and target (t_eff)."""
    adv, dis = [], []
    if "hidden" in a_eff:
        adv.append("attacker_hidden")
    if "prone" in a_eff:
        dis.append("attacker_prone")
    if "restrained" in a_eff:
        dis.append("attacker_restrained")
    if "prone" in t_eff:
        (adv if kind == "melee" else dis).append("target_prone")
    if "restrained" in t_eff:
        adv.append("target_restrained")
    if "unconscious" in t_eff:
        adv.append("target_unconscious")
    if "hidden" in t_eff:
        dis.append("target_hidden")
    return adv, dis


def flying_capable(data: dict) -> bool:
    """A combatant can fly if its stat data says so (bestiary `flying: true`)
    or it carries an effect named `flying` (PC granted by spell/item)."""
    if data.get("flying"):
        return True
    return "flying" in {e["name"] for e in data.get("effects", [])}


def is_living(root: Path, enc: dict, cid: str) -> bool:
    if cid in enc["monsters"]:
        return not enc["monsters"][cid].get("dead", False)
    _, data, _ = resolve_actor(root, cid)
    return "dead" not in {e["name"] for e in data.get("effects", [])}


def adjacent_living_hostile(root: Path, enc: dict, attacker: str) -> bool:
    """True if a living, cross-side combatant is chebyshev-adjacent to attacker."""
    if attacker not in enc["positions"]:
        return False
    pos = tuple(enc["positions"][attacker])
    attacker_is_monster = attacker in enc["monsters"]
    for cid, cpos in enc["positions"].items():
        if cid == attacker:
            continue
        if (cid in enc["monsters"]) == attacker_is_monster:
            continue  # same side, not hostile
        if grid.chebyshev(pos, tuple(cpos)) != 1:
            continue
        if is_living(root, enc, cid):
            return True
    return False


def _hostiles_of(root: Path, enc: dict, actor: str, *, awake: bool = True):
    """Living cross-side combatants as (cid, data, pos) tuples; with awake,
    skips unconscious ones (they can't see or distract anyone)."""
    actor_is_monster = actor in enc["monsters"]
    for cid, cpos in enc["positions"].items():
        if cid == actor or (cid in enc["monsters"]) == actor_is_monster:
            continue
        if not is_living(root, enc, cid):
            continue
        _, data = get_combatant(root, enc, cid)
        if awake and "unconscious" in effect_names(data):
            continue
        yield cid, data, tuple(cpos)


def ally_adjacent(root: Path, enc: dict, attacker: str, target: str) -> bool:
    """A living, conscious combatant on the attacker's side (other than the
    attacker itself) is chebyshev-adjacent to the target."""
    if target not in enc["positions"]:
        return False
    tpos = tuple(enc["positions"][target])
    attacker_is_monster = attacker in enc["monsters"]
    for cid, cpos in enc["positions"].items():
        if cid in (attacker, target):
            continue
        if (cid in enc["monsters"]) != attacker_is_monster:
            continue  # hostile, not an ally
        if grid.chebyshev(tpos, tuple(cpos)) != 1:
            continue
        if not is_living(root, enc, cid):
            continue
        _, data = get_combatant(root, enc, cid)
        if "unconscious" not in effect_names(data):
            return True
    return False


def start(root: Path, g: dict, map_rel: str, rng: Random, pcs: list[str] | None = None) -> dict:
    if (root / "state" / "encounter.yaml").exists():
        raise EngineError("encounter_active", "an encounter is already running")
    map_rel = map_rel.removeprefix("canon/")
    emap = worldfs.read_yaml(root / "canon" / map_rel)
    party = worldfs.read_yaml(worldfs.state(root, "party"))
    if not party["members"]:
        raise EngineError("no_party", "no PCs in the party")

    sheets = {pid: worldfs.read_yaml(worldfs.state(root, f"party/{pid}"))
              for pid in party["members"]}

    def is_living(pid):
        return "dead" not in {e["name"] for e in sheets[pid]["effects"]}

    if pcs is None:
        participants = [pid for pid in party["members"] if is_living(pid)]
    else:
        participants = pcs
        for pid in participants:
            if pid not in party["members"]:
                raise EngineError("not_found", f"no combatant {pid}")
            if not is_living(pid):
                raise EngineError("dead", f"{pid} is dead and cannot join the encounter")
    if not participants:
        raise EngineError("no_party", "no living PCs to seat")

    if len(participants) > len(emap["pc_spawns"]):
        raise EngineError("map_invalid", "not enough pc_spawns for the party")

    here = worldfs.pc_location(sheets[participants[0]], party)
    for pid in participants[1:]:
        loc = worldfs.pc_location(sheets[pid], party)
        if loc != here:
            raise EngineError("split_party", f"{pid} is at {loc}, not {here}")

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
                         "flying": entry.get("flying", False),
                         "effects": [], "dead": False}
        positions[mid] = list(spec["pos"])
    for pc_id, spawn in zip(participants, emap["pc_spawns"]):
        positions[pc_id] = list(spawn)
    init = g.get("combat", {}).get("initiative", {})
    init_sides = int(str(init.get("die", "d20")).lstrip("dD"))
    init_attr = init.get("attr", "DEX")
    scores = {}
    for cid in [*participants, *monsters]:
        _, data = get_combatant(root, {"monsters": monsters}, cid)
        attr_score = data["attributes"][init_attr]
        scores[cid] = (rng.randint(1, init_sides) + attr_mod(attr_score), attr_score, cid)
    order = sorted(scores, key=lambda c: scores[c], reverse=True)
    enc = {"id": emap["id"], "name": emap["name"], "round": 1, "turn": 0,
           "order": order, "grid": emap["grid"], "terrain": emap.get("terrain", []),
           "dark": bool(emap.get("dark")),
           "positions": positions, "monsters": monsters, "pcs": participants}
    save_encounter(root, enc)
    timeline.append_event(root, type_="encounter", actors=order,
                          summary=f"encounter started: {emap['name']}")
    return {"id": enc["id"], "order": order,
            "initiative": {c: scores[c][0] for c in order}}


def next_turn(root: Path, rng: Random | None = None) -> dict:
    enc = load_encounter(root)
    enc["turn"] += 1
    expired = []
    falling = []
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
            if (any(name == "flying" for c, name in expired if c == cid)
                    and enc.get("aloft", {}).get(cid) and not flying_capable(data)
                    and rng is not None):
                falling.append(cid)
    save_encounter(root, enc)
    result = {"round": enc["round"], "turn": enc["turn"],
              "up": enc["order"][enc["turn"]], "expired_effects": expired}
    if falling:
        result["fell"] = [fall(root, cid, rng) for cid in falling]
    return result


def end(root: Path, g: dict, rng: Random) -> dict:
    enc = load_encounter(root)
    party = worldfs.read_yaml(worldfs.state(root, "party"))
    participants = enc.get("pcs") or list(party["members"])
    total_xp = sum(m["xp"] for m in enc["monsters"].values())
    xp_each = total_xp // len(participants)
    for i, pc_id in enumerate(participants):
        sheet = worldfs.read_yaml(worldfs.state(root, f"party/{pc_id}"))
        sheet["xp"] += xp_each + (total_xp % len(participants) if i == 0 else 0)
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


def apply_damage(root: Path, target: str, amount: int, source: str,
                 rng: Random | None = None) -> dict:
    kind, data, enc = resolve_actor(root, target)
    before = data["hp"]
    data["hp"] = max(0, before - amount)
    dropped = data["hp"] == 0 and before > 0
    released, fall_damage = [], None
    if dropped:
        if kind == "monster":
            data["dead"] = True
        else:
            names = effect_names(data)
            data["effects"] += [{"name": n, "duration": -1}
                                for n in ("unconscious", "dying") if n not in names]
            data["death_saves"] = {"successes": 0, "fails": 0}
        if enc:
            for held, holder in list(enc.get("grapples", {}).items()):
                if holder != target:
                    continue
                hkind, hdata = (kind, data) if held == target \
                    else get_combatant(root, enc, held)
                hdata["effects"] = [e for e in hdata["effects"] if e["name"] != "grappled"]
                if hkind == "pc":
                    save_pc(root, hdata)
                del enc["grapples"][held]
                released.append(held)
            if enc.get("aloft", {}).get(target) and rng is not None:
                enc["aloft"][target] = False
                fall_damage = dice.roll("2d6", rng).total
                data["hp"] = max(0, data["hp"] - fall_damage)
                if "prone" not in effect_names(data):
                    data["effects"].append({"name": "prone", "duration": -1})
    _persist(root, kind, data, enc)
    timeline.append_event(root, type_="damage", actors=[target],
                          summary=f"{target} takes {amount} damage ({source})",
                          delta={target: {"hp": [before, data["hp"]]}})
    if fall_damage is not None:
        timeline.append_event(root, type_="damage", actors=[target],
                              summary=f"{target} drops from the air and falls prone"
                                      f" ({fall_damage} fall damage)")
    for held in released:
        timeline.append_event(root, type_="effect", actors=[target, held],
                              summary=f"{target} drops and loses its grip on {held}")
    result = {"target": target, "amount": amount, "hp": [before, data["hp"]],
              "dropped": dropped}
    if released:
        result["grapples_released"] = released
    if fall_damage is not None:
        result["fell"] = fall_damage
    return result


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


def resolve_hit(natural: int, total: int, ac: int, *,
                crit_on: int = 20, fumble_on: int = 1) -> tuple[bool, str | None]:
    """Shared hit/crit resolution: a natural `fumble_on` always misses, a
    natural `crit_on` always hits and crits, otherwise compare the total to
    AC. `crit_on`/`fumble_on` come from the ruleset's core.yaml. Returns
    (hit, crit) where crit is 'hit' | 'fumble' | None."""
    crit = "hit" if natural == crit_on else "fumble" if natural == fumble_on else None
    hit = natural != fumble_on and (natural == crit_on or total >= ac)
    return hit, crit


def crit_bounds(g: dict) -> tuple[int, int]:
    """(crit_on, fumble_on) from the ruleset, defaulting to 20 / 1."""
    core = g.get("core", {})
    return core.get("crit_on", 20), core.get("fumble_on", 1)


def roll_damage(expr, rng: Random, crit: str | None) -> int:
    """Roll a damage expression; on a crit, double the dice (not the modifier),
    matching a fresh re-roll of just the dice."""
    dmg = dice.roll(str(expr), rng).total
    if crit == "hit":
        dmg += sum(dice.roll(str(expr), rng).rolls)
    return dmg


def check_reach(enc: dict, a_pos, b_pos, max_range: int, *,
                a_label: str, b_label: str) -> None:
    """Raise if b is out of range of a or blocked from line of sight."""
    dist = grid.chebyshev(a_pos, b_pos)
    if dist > max_range:
        raise EngineError("out_of_range", f"{b_label} is {dist} away, range is {max_range}")
    if not grid.line_of_sight(enc, a_pos, b_pos):
        raise EngineError("no_los", f"{a_label} has no line of sight to {b_label}")


def same_plane(enc: dict, a: str, b: str) -> bool:
    """Two combatants share a plane unless exactly one of them is aloft."""
    aloft = enc.get("aloft", {})
    return bool(aloft.get(a)) == bool(aloft.get(b))


def attack(root: Path, attacker: str, target: str, *, attack_name: str | None,
           adv: bool, dis: bool, roll_fn, rng: Random) -> dict:
    a_kind, a_data, enc = resolve_actor(root, attacker)
    _, t_data, _ = resolve_actor(root, target)
    attacks = a_data["attacks"]
    atk = next((a for a in attacks if a["name"] == attack_name), attacks[0] if attacks else None)
    if atk is None:
        raise EngineError("no_attack", f"{attacker} has no attack {attack_name!r}")
    kind = attack_kind(atk)
    if enc and attacker in enc["positions"] and target in enc["positions"]:
        a_pos = tuple(enc["positions"][attacker])
        t_pos = tuple(enc["positions"][target])
        check_reach(enc, a_pos, t_pos, atk.get("range", 1), a_label=attacker, b_label=target)
        if kind == "melee" and not same_plane(enc, attacker, target):
            if enc.get("aloft", {}).get(target):
                raise EngineError("unreachable", f"{target} is airborne")
            raise EngineError("unreachable",
                              "attacker is airborne, cannot reach a grounded target")
    ranged_in_melee = (kind == "ranged" and enc is not None
                      and adjacent_living_hostile(root, enc, attacker))
    a_eff, t_eff = effect_names(a_data), effect_names(t_data)
    adv_from, dis_from = roll_conditions(a_eff, t_eff, kind)
    dis_from += [f"attacker_{r}" for r in self_dis_conditions(root, enc, attacker, a_data)]
    if in_darkness(enc, target, t_data):
        dis_from.append("target_in_darkness")
    if in_darkness(enc, attacker, a_data):
        adv_from.append("attacker_in_darkness")
    if adv:
        adv_from.insert(0, "caller")
    if dis:
        dis_from.insert(0, "caller")
    if ranged_in_melee:
        dis_from.append("ranged_in_melee")
    eff_adv, eff_dis = bool(adv_from), bool(dis_from)
    natural, total = roll_fn(atk["attack_mod"], eff_adv, eff_dis)
    crit_on, fumble_on = crit_bounds(worldfs.load_game_for(root))
    hit, crit = resolve_hit(natural, total, t_data["ac"], crit_on=crit_on, fumble_on=fumble_on)
    damage = roll_damage(atk["damage"], rng, crit) if hit else 0
    result = {"attacker": attacker, "target": target, "attack": atk["name"],
              "natural": natural, "total": total, "vs_ac": t_data["ac"],
              "hit": hit, "crit": crit, "damage": damage}
    if ranged_in_melee:
        result["ranged_in_melee"] = True
    if adv_from:
        result["adv_from"] = adv_from
    if dis_from:
        result["dis_from"] = dis_from
    mutated = False
    if hit and a_kind == "pc" and "sneak_attack" in a_data.get("features", []):
        used = enc is not None and enc.get("sneak_used", {}).get(attacker) == enc["round"]
        distracted = enc is not None and ally_adjacent(root, enc, attacker, target)
        if not eff_dis and not used and (eff_adv or distracted):
            n_dice = min(3, (a_data["level"] + 1) // 2)
            sneak = dice.roll(f"{n_dice}d6", rng).total
            if crit == "hit":
                sneak += dice.roll(f"{n_dice}d6", rng).total
            damage += sneak
            result["damage"] = damage
            result["sneak_attack"] = sneak
            if enc is not None:
                enc.setdefault("sneak_used", {})[attacker] = enc["round"]
                mutated = True
    if reveal_actor(root, enc, attacker, a_data, a_kind, "attacked from hiding"):
        result["revealed"] = True
        mutated = True
    if mutated:
        _persist(root, a_kind, a_data, enc)
    verb = "hits" if hit else "misses"
    timeline.append_event(root, type_="attack", actors=[attacker, target],
                          summary=f"{attacker} {verb} {target} with {atk['name']}"
                                  + (f" for {damage}" if hit else ""))
    if hit and damage:
        dmg_result = apply_damage(root, target, damage,
                                  source=f"{attacker}:{atk['name']}", rng=rng)
        result["target_hp"] = dmg_result["hp"]
        result["dropped"] = dmg_result["dropped"]
    return result


def set_effect(root: Path, target: str, name: str, duration: int,
               source: str | None = None) -> dict:
    kind, data, enc = resolve_actor(root, target)
    data["effects"] = [e for e in data["effects"] if e["name"] != name]
    entry = {"name": name, "duration": duration}
    if source:
        entry["source"] = source
    data["effects"].append(entry)
    _persist(root, kind, data, enc)
    timeline.append_event(root, type_="effect", actors=[target],
                          summary=f"{target} gains {name} ({duration} rounds)"
                                  + (f" from {source}" if source else ""))
    return {"target": target, "effects": data["effects"]}


def remove_effect(root: Path, target: str, name: str,
                  rng: Random | None = None) -> dict:
    kind, data, enc = resolve_actor(root, target)
    data["effects"] = [e for e in data["effects"] if e["name"] != name]
    if enc is not None:
        if name == "hidden":
            enc.get("stealth", {}).pop(target, None)
        if name == "grappled":
            enc.get("grapples", {}).pop(target, None)
    _persist(root, kind, data, enc)
    timeline.append_event(root, type_="effect", actors=[target],
                          summary=f"{target} loses {name}")
    result = {"target": target, "effects": data["effects"]}
    if (name == "flying" and enc is not None and enc.get("aloft", {}).get(target)
            and not flying_capable(data) and rng is not None):
        result["fell"] = fall(root, target, rng)
    return result


def death_save(root: Path, actor: str, *, roll_fn) -> dict:
    kind, sheet, enc = resolve_actor(root, actor)
    if kind != "pc" or "dying" not in {e["name"] for e in sheet["effects"]}:
        raise EngineError("not_dying", f"{actor} is not dying")
    cfg = worldfs.load_game_for(root).get("recovery", {}).get("death_save", {})
    dc = cfg.get("dc", 10)
    fails_to_die = cfg.get("fails_to_die", 3)
    successes_to_stable = cfg.get("successes_to_stable", 3)
    crit_on, fumble_on = crit_bounds(worldfs.load_game_for(root))
    natural, _ = roll_fn(0, False, False)
    saves = sheet.setdefault("death_saves", {"successes": 0, "fails": 0})
    if natural == crit_on:
        result = "revived"
    elif natural >= dc:
        saves["successes"] += 1
        result = "stable" if saves["successes"] >= successes_to_stable else "success"
    else:
        saves["fails"] += 1
        result = "dead" if saves["fails"] >= fails_to_die else "fail"
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


def ascend(root: Path, actor: str) -> dict:
    enc = load_encounter(root)
    if actor not in enc["positions"]:
        raise EngineError("not_found", f"{actor} is not on the map")
    _, data = get_combatant(root, enc, actor)
    if not flying_capable(data):
        raise EngineError("cannot_fly", f"{actor} cannot fly")
    for cond in ("grappled", "restrained"):
        if cond in effect_names(data):
            raise EngineError("held", f"{actor} is {cond} and cannot take off")
    enc.setdefault("aloft", {})[actor] = True
    save_encounter(root, enc)
    timeline.append_event(root, type_="move", actors=[actor],
                          summary=f"{actor} takes to the air")
    return {"actor": actor, "aloft": True}


def land(root: Path, actor: str) -> dict:
    enc = load_encounter(root)
    if actor not in enc["positions"]:
        raise EngineError("not_found", f"{actor} is not on the map")
    enc.setdefault("aloft", {})[actor] = False
    save_encounter(root, enc)
    timeline.append_event(root, type_="move", actors=[actor], summary=f"{actor} lands")
    return {"actor": actor, "aloft": False}


def fall(root: Path, actor: str, rng: Random, expr: str = "2d6") -> dict:
    enc = load_encounter(root)
    if not enc.get("aloft", {}).get(actor):
        raise EngineError("not_aloft", f"{actor} is not aloft")
    enc["aloft"][actor] = False
    save_encounter(root, enc)
    timeline.append_event(root, type_="move", actors=[actor],
                          summary=f"{actor} falls from the sky")
    dmg = dice.roll(expr, rng).total
    damage_result = apply_damage(root, actor, dmg, source="fall", rng=rng)
    kind, data, enc = resolve_actor(root, actor)
    if "prone" not in effect_names(data):
        data["effects"].append({"name": "prone", "duration": -1})
        _persist(root, kind, data, enc)
    return {"actor": actor, "damage": dmg, "hp": damage_result["hp"],
            "prone": True, "dropped": damage_result["dropped"]}


def sight(root: Path, actor: str, target: str) -> dict:
    enc = load_encounter(root)
    for cid in (actor, target):
        if cid not in enc["positions"]:
            raise EngineError("not_found", f"{cid} is not on the map")
    a, b = tuple(enc["positions"][actor]), tuple(enc["positions"][target])
    return {"actor": actor, "target": target,
            "distance": grid.chebyshev(a, b),
            "los": grid.line_of_sight(enc, a, b)}


def hide(root: Path, g: dict, actor: str, *, roll_fn) -> dict:
    enc = load_encounter(root)
    if actor not in enc["positions"]:
        raise EngineError("not_found", f"{actor} is not on the map")
    kind, data = get_combatant(root, enc, actor)
    eff = effect_names(data)
    for cond in ("grappled", "restrained"):
        if cond in eff:
            raise EngineError("held",
                              f"{actor} is {cond}; whatever holds it knows where it is")
    pos = tuple(enc["positions"][actor])
    dark = in_darkness(enc, actor, data)
    if not dark:  # darkness is concealment; otherwise cover must block every hostile
        seen_by = sorted(cid for cid, _, cpos in _hostiles_of(root, enc, actor)
                         if grid.line_of_sight(enc, cpos, pos))
        if seen_by:
            raise EngineError("seen", f"{actor} is in plain sight of {', '.join(seen_by)}")
    adv_from, dis_from = [], []
    if "silent_step" in eff:
        adv_from.append("silent_step")
    dis_from += self_dis_conditions(root, enc, actor, data)
    for line in data.get("inventory", []):
        if line.get("equipped") and g["items"][line["item"]].get("stealth_dis"):
            dis_from.append(f"noisy:{line['item']}")
    natural, total = roll_fn(skill_mod(data, "DEX", "stealth"),
                             bool(adv_from), bool(dis_from))
    data["effects"] = [e for e in data["effects"] if e["name"] != "hidden"]
    data["effects"].append({"name": "hidden", "duration": -1})
    enc.setdefault("stealth", {})[actor] = total
    if kind == "pc":
        save_pc(root, data)
    save_encounter(root, enc)
    timeline.append_event(root, type_="effect", actors=[actor],
                          summary=f"{actor} hides (stealth {total})")
    result = {"actor": actor, "natural": natural, "stealth": total, "hidden": True}
    if dark:
        result["in_darkness"] = True
    if adv_from:
        result["adv_from"] = adv_from
    if dis_from:
        result["dis_from"] = dis_from
    return result


def stand(root: Path, actor: str) -> dict:
    kind, data, enc = resolve_actor(root, actor)
    if "prone" not in effect_names(data):
        raise EngineError("not_prone", f"{actor} is not prone")
    data["effects"] = [e for e in data["effects"] if e["name"] != "prone"]
    _persist(root, kind, data, enc)
    timeline.append_event(root, type_="effect", actors=[actor],
                          summary=f"{actor} stands up")
    return {"actor": actor, "effects": data["effects"]}


def reveal_actor(root: Path, enc, cid: str, data: dict, kind: str, note: str) -> bool:
    """Strip hidden from a combatant that just gave itself away (by attacking,
    casting, grappling, …). Saves the PC sheet; the caller persists the
    encounter. Returns whether a reveal actually happened."""
    if "hidden" not in effect_names(data):
        return False
    data["effects"] = [e for e in data["effects"] if e["name"] != "hidden"]
    if enc is not None:
        enc.get("stealth", {}).pop(cid, None)
    if kind == "pc":
        save_pc(root, data)
    timeline.append_event(root, type_="effect", actors=[cid],
                          summary=f"{cid} is revealed ({note})")
    return True


def _contest(attacker_mod: int, defender_mod: int, roll_fn,
             a_dis: list[str] | None = None, d_dis: list[str] | None = None) -> dict:
    """Contested check; ties go to the defender. Each side rolls at
    disadvantage if it carries impairing conditions (poisoned, frightened)."""
    a_nat, a_total = roll_fn(attacker_mod, False, bool(a_dis))
    d_nat, d_total = roll_fn(defender_mod, False, bool(d_dis))
    out = {"attacker": {"natural": a_nat, "total": a_total},
           "defender": {"natural": d_nat, "total": d_total},
           "success": a_total > d_total}
    if a_dis:
        out["attacker"]["dis_from"] = a_dis
    if d_dis:
        out["defender"]["dis_from"] = d_dis
    return out


def _require_grabbable(enc: dict, actor: str, target: str) -> None:
    for cid in (actor, target):
        if cid not in enc["positions"]:
            raise EngineError("not_found", f"{cid} is not on the map")
    dist = grid.chebyshev(tuple(enc["positions"][actor]), tuple(enc["positions"][target]))
    if dist > 1:
        raise EngineError("out_of_range", f"{target} is {dist} away, must be adjacent")
    if not same_plane(enc, actor, target):
        raise EngineError("unreachable", f"{actor} and {target} are not on the same plane")


def _escape_mod(data: dict) -> int:
    return max(skill_mod(data, "STR", "athletics"), skill_mod(data, "DEX", "acrobatics"))


def grapple(root: Path, actor: str, target: str, *, roll_fn, release: bool = False) -> dict:
    enc = load_encounter(root)
    if release:
        if enc.get("grapples", {}).get(target) != actor:
            raise EngineError("not_grappling", f"{actor} is not grappling {target}")
        tkind, tdata = get_combatant(root, enc, target)
        tdata["effects"] = [e for e in tdata["effects"] if e["name"] != "grappled"]
        if tkind == "pc":
            save_pc(root, tdata)
        del enc["grapples"][target]
        save_encounter(root, enc)
        timeline.append_event(root, type_="effect", actors=[actor, target],
                              summary=f"{actor} releases {target}")
        return {"actor": actor, "target": target, "released": True}
    _require_grabbable(enc, actor, target)
    if not is_living(root, enc, target):
        raise EngineError("invalid_target", f"{target} is down")
    if target in enc.get("grapples", {}):
        raise EngineError("already_grappled", f"{target} is already grappled")
    a_kind, a_data = get_combatant(root, enc, actor)
    tkind, tdata = get_combatant(root, enc, target)
    revealed = reveal_actor(root, enc, actor, a_data, a_kind, "lunged from hiding")
    contest = _contest(skill_mod(a_data, "STR", "athletics"), _escape_mod(tdata), roll_fn,
                       a_dis=self_dis_conditions(root, enc, actor, a_data),
                       d_dis=self_dis_conditions(root, enc, target, tdata))
    if contest["success"]:
        tdata["effects"] = [e for e in tdata["effects"] if e["name"] != "grappled"]
        tdata["effects"].append({"name": "grappled", "duration": -1})
        if tkind == "pc":
            save_pc(root, tdata)
        enc.setdefault("grapples", {})[target] = actor
    if contest["success"] or revealed:
        save_encounter(root, enc)
    verb = "grapples" if contest["success"] else "fails to grapple"
    timeline.append_event(root, type_="effect", actors=[actor, target],
                          summary=f"{actor} {verb} {target}")
    result = {"actor": actor, "target": target, "contest": contest,
              "grappled": contest["success"]}
    if revealed:
        result["revealed"] = True
    return result


def escape(root: Path, actor: str, *, roll_fn) -> dict:
    enc = load_encounter(root)
    holder = enc.get("grapples", {}).get(actor)
    if holder is None:
        raise EngineError("not_grappled", f"{actor} is not grappled")
    akind, a_data = get_combatant(root, enc, actor)
    _, h_data = get_combatant(root, enc, holder)
    contest = _contest(_escape_mod(a_data), skill_mod(h_data, "STR", "athletics"), roll_fn,
                       a_dis=self_dis_conditions(root, enc, actor, a_data),
                       d_dis=self_dis_conditions(root, enc, holder, h_data))
    if contest["success"]:
        a_data["effects"] = [e for e in a_data["effects"] if e["name"] != "grappled"]
        if akind == "pc":
            save_pc(root, a_data)
        del enc["grapples"][actor]
        save_encounter(root, enc)
    verb = "breaks free of" if contest["success"] else "fails to break free of"
    timeline.append_event(root, type_="effect", actors=[actor, holder],
                          summary=f"{actor} {verb} {holder}")
    return {"actor": actor, "holder": holder, "contest": contest,
            "escaped": contest["success"]}


def shove(root: Path, actor: str, target: str, *, roll_fn) -> dict:
    enc = load_encounter(root)
    _require_grabbable(enc, actor, target)
    if not is_living(root, enc, target):
        raise EngineError("invalid_target", f"{target} is down")
    a_kind, a_data = get_combatant(root, enc, actor)
    tkind, tdata = get_combatant(root, enc, target)
    revealed = reveal_actor(root, enc, actor, a_data, a_kind, "lunged from hiding")
    contest = _contest(skill_mod(a_data, "STR", "athletics"), _escape_mod(tdata), roll_fn,
                       a_dis=self_dis_conditions(root, enc, actor, a_data),
                       d_dis=self_dis_conditions(root, enc, target, tdata))
    if contest["success"]:
        tdata["effects"] = [e for e in tdata["effects"] if e["name"] != "prone"]
        tdata["effects"].append({"name": "prone", "duration": -1})
        if tkind == "pc":
            save_pc(root, tdata)
    if contest["success"] or revealed:
        save_encounter(root, enc)
    verb = "shoves" if contest["success"] else "fails to shove"
    timeline.append_event(root, type_="effect", actors=[actor, target],
                          summary=f"{actor} {verb} {target}"
                                  + (" prone" if contest["success"] else ""))
    result = {"actor": actor, "target": target, "contest": contest,
              "prone": contest["success"]}
    if revealed:
        result["revealed"] = True
    return result


def move(root: Path, actor: str, to: tuple[int, int], *, force: bool = False) -> dict:
    enc = load_encounter(root)
    if actor not in enc["positions"]:
        raise EngineError("not_found", f"{actor} is not on the map")
    src = tuple(enc["positions"][actor])
    to = tuple(to)
    reason = grid.blocked(enc, to)
    if reason == "oob" or (reason and not force):
        raise EngineError("blocked", f"cannot enter {list(to)}: {reason}")
    kind, data = get_combatant(root, enc, actor)
    eff = effect_names(data)
    aloft = bool(enc.get("aloft", {}).get(actor))
    if force:
        cost = grid.chebyshev(src, to)
    else:
        for cond in ("grappled", "restrained"):
            if cond in eff:
                raise EngineError("held", f"{actor} is {cond} and cannot move")
        fear = next((e for e in data.get("effects", []) if e["name"] == "frightened"), None)
        fear_src = (fear or {}).get("source")
        if (fear_src and fear_src in enc["positions"] and is_living(root, enc, fear_src)):
            src_pos = tuple(enc["positions"][fear_src])
            if grid.chebyshev(to, src_pos) < grid.chebyshev(src, src_pos):
                raise EngineError("frightened",
                                  f"{actor} cannot willingly move closer to {fear_src}")
        hostile_cells = (set() if aloft else
                         {pos for cid, _, pos in _hostiles_of(root, enc, actor, awake=False)
                          if not enc.get("aloft", {}).get(cid)})
        diagonal_cost = worldfs.load_game_for(root).get("combat", {}).get("diagonal_cost", 1)
        cost = grid.path_cost(enc, src, to, ignore_terrain=aloft,
                              impassable=hostile_cells, diagonal_cost=diagonal_cost)
        if cost is None:
            raise EngineError("no_path", f"no route from {list(src)} to {list(to)}")
        if "prone" in eff:
            cost *= 2  # crawling
        if cost > data["speed"]:
            raise EngineError("too_far", f"cost {cost} exceeds speed {data['speed']}")
    enc["positions"][actor] = list(to)
    result = {"actor": actor, "from": list(src), "to": list(to),
              "cost": cost, "forced": force}
    # a grapple breaks the moment the pair is no longer adjacent
    for held, holder in list(enc.get("grapples", {}).items()):
        if actor not in (held, holder):
            continue
        other = holder if actor == held else held
        if other not in enc["positions"]:
            continue
        if grid.chebyshev(to, tuple(enc["positions"][other])) <= 1:
            continue
        hkind, hdata = (kind, data) if held == actor else get_combatant(root, enc, held)
        hdata["effects"] = [e for e in hdata["effects"] if e["name"] != "grappled"]
        if hkind == "pc":
            save_pc(root, hdata)
        del enc["grapples"][held]
        result["grapple_broken"] = [holder, held]
        timeline.append_event(root, type_="effect", actors=[holder, held],
                              summary=f"{holder} loses its grip on {held}")
    if "hidden" in eff and not in_darkness(enc, actor, data):
        stealth = enc.get("stealth", {}).get(actor, 0)
        spotters = [cid for cid, cdata, cpos in _hostiles_of(root, enc, actor)
                    if grid.line_of_sight(enc, cpos, to)
                    and passive_perception(cdata) >= stealth]
        if spotters:
            data["effects"] = [e for e in data["effects"] if e["name"] != "hidden"]
            enc.get("stealth", {}).pop(actor, None)
            if kind == "pc":
                save_pc(root, data)
            result["revealed_by"] = sorted(spotters)
            timeline.append_event(root, type_="effect", actors=[actor, *spotters],
                                  summary=f"{actor} is spotted by {', '.join(sorted(spotters))}")
    # ...and the mover may walk around someone else's cover: its passive
    # perception contests each hidden hostile its new position can see
    if "unconscious" not in eff:
        pp = passive_perception(data)
        spotted = []
        for cid, cdata, cpos in _hostiles_of(root, enc, actor, awake=False):
            if "hidden" not in effect_names(cdata):
                continue
            if in_darkness(enc, cid, cdata):
                continue  # nobody sees into darkness
            if not grid.line_of_sight(enc, to, cpos):
                continue
            if pp < enc.get("stealth", {}).get(cid, 0):
                continue
            cdata["effects"] = [e for e in cdata["effects"] if e["name"] != "hidden"]
            enc.get("stealth", {}).pop(cid, None)
            if cid not in enc["monsters"]:
                save_pc(root, cdata)
            spotted.append(cid)
        if spotted:
            result["spotted"] = sorted(spotted)
            timeline.append_event(root, type_="effect", actors=[actor, *spotted],
                                  summary=f"{actor} spots {', '.join(sorted(spotted))}")
    save_encounter(root, enc)
    timeline.append_event(root, type_="move", actors=[actor],
                          summary=f"{actor} moves {list(src)} -> {list(to)}")
    return result
