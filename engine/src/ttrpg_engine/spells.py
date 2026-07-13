from pathlib import Path
from random import Random

from ttrpg_engine import combat, dice, grid, timeline, worldfs
from ttrpg_engine.chargen import attr_mod
from ttrpg_engine.errors import EngineError


def _expr(template: str, castmod: int) -> str:
    return str(template).replace("+CASTMOD", f"{castmod:+d}")


def _resolve_save(sheet, castmod, c_data, spell, roll_fn):
    dc = 8 + sheet["proficiency"] + castmod
    natural, _ = roll_fn(0, False, False)
    total = natural + attr_mod(c_data["attributes"][spell["save_attr"]])
    saved = total >= dc
    entry = {"attr": spell["save_attr"], "dc": dc, "total": total, "success": saved}
    lands, half = True, False
    if saved:
        lands, half = spell.get("on_save", "none") == "half", spell.get("on_save") == "half"
    return entry, lands, half


def _spend_slot(root, sheet, level):
    if level > 0:
        slot = sheet["spell_slots"].get(level)
        if not slot or slot["current"] < 1:
            raise EngineError("no_slots", f"no level-{level} slots left")
        slot["current"] -= 1
        combat.save_pc(root, sheet)


def cast(root: Path, g: dict, caster: str, spell_name: str, target: str | None,
         *, roll_fn, rng: Random, at: tuple[int, int] | None = None) -> dict:
    kind, sheet, enc = combat.resolve_actor(root, caster)
    if kind != "pc":
        raise EngineError("not_pc", "only PCs cast via their sheets in v1")
    if spell_name not in g["spells"]:
        raise EngineError("unknown_spell", f"no spell {spell_name}")
    if spell_name not in sheet["spells_known"]:
        raise EngineError("unknown_spell", f"{caster} does not know {spell_name}")
    spell = g["spells"][spell_name]
    area = spell.get("area")
    if area and target is not None:
        raise EngineError("area_needs_cell", f"{spell_name} is an area spell; use --at, not --target")
    if area and at is None:
        raise EngineError("area_needs_cell", f"{spell_name} requires --at CELL")
    if not area and at is not None:
        raise EngineError("not_area", f"{spell_name} is not an area spell; use --target, not --at")
    cast_attr = g["classes"][sheet["class"]]["cast_attr"]
    castmod = attr_mod(sheet["attributes"][cast_attr])
    level = spell["level"]

    if area:
        if enc is None:
            raise EngineError("no_encounter", "area spells require an active encounter")
        cell = tuple(at)
        if caster in enc["positions"]:
            dist = grid.chebyshev(tuple(enc["positions"][caster]), cell)
            if dist > spell["range"]:
                raise EngineError("out_of_range", f"{list(cell)} is {dist} away, range {spell['range']}")
        _spend_slot(root, sheet, level)
        radius = area["radius"]
        affected = [cid for cid, pos in enc["positions"].items()
                   if grid.chebyshev(tuple(pos), cell) <= radius and combat.is_living(root, enc, cid)]
        timeline.append_event(root, type_="cast", actors=[caster, *affected],
                              summary=f"{caster} casts {spell_name} at {list(cell)}"
                                      + (f" (hits {', '.join(affected)})" if affected else " (hits nothing)"))
        result = {"caster": caster, "spell": spell_name, "cell": list(cell),
                  "targets": [], "slot_level": level or None}
        for cid in affected:
            _, c_data, _ = combat.resolve_actor(root, cid)
            entry = {"id": cid}
            lands, half = True, False
            if spell["resolve"] == "save":
                save_entry, lands, half = _resolve_save(sheet, castmod, c_data, spell, roll_fn)
                entry["save"] = save_entry
            if lands:
                if "damage" in spell:
                    dmg = dice.roll(_expr(spell["damage"], castmod), rng).total
                    dmg = max(1, dmg // 2) if half else dmg
                    entry["damage"] = combat.apply_damage(root, cid, dmg,
                                                          source=f"{caster}:{spell_name}")["amount"]
                if "heal" in spell:
                    amount = dice.roll(_expr(spell["heal"], castmod), rng).total
                    entry["healed"] = combat.apply_heal(root, cid, amount,
                                                        source=f"{caster}:{spell_name}")["amount"]
            result["targets"].append(entry)
        return result

    target = target or caster
    _, t_data, _ = combat.resolve_actor(root, target)
    if enc and caster in enc["positions"] and target in enc["positions"]:
        dist = grid.chebyshev(tuple(enc["positions"][caster]),
                              tuple(enc["positions"][target]))
        if dist > spell["range"]:
            raise EngineError("out_of_range", f"{target} is {dist} away, range {spell['range']}")
    _spend_slot(root, sheet, level)
    result = {"caster": caster, "spell": spell_name, "target": target,
              "slot_level": level or None, "damage": 0, "healed": 0}
    lands, half = True, False
    if spell["resolve"] == "attack":
        ranged_in_melee = (spell["range"] > 1 and enc is not None
                           and combat.adjacent_living_hostile(root, enc, caster))
        natural, total = roll_fn(sheet["proficiency"] + castmod, False, ranged_in_melee)
        lands = natural != 1 and (natural == 20 or total >= t_data["ac"])
        result["attack"] = {"natural": natural, "total": total, "vs_ac": t_data["ac"], "hit": lands}
        if ranged_in_melee:
            result["ranged_in_melee"] = True
    elif spell["resolve"] == "save":
        save_entry, lands, half = _resolve_save(sheet, castmod, t_data, spell, roll_fn)
        result["save"] = save_entry
    timeline.append_event(root, type_="cast", actors=[caster, target],
                          summary=f"{caster} casts {spell_name} at {target}")
    if lands:
        if "damage" in spell:
            dmg = dice.roll(_expr(spell["damage"], castmod), rng).total
            dmg = max(1, dmg // 2) if half else dmg
            result["damage"] = combat.apply_damage(root, target, dmg,
                                                   source=f"{caster}:{spell_name}")["amount"]
        if "heal" in spell:
            amount = dice.roll(_expr(spell["heal"], castmod), rng).total
            result["healed"] = combat.apply_heal(root, target, amount,
                                                 source=f"{caster}:{spell_name}")["amount"]
        if "effect" in spell:
            combat.set_effect(root, target, spell["effect"]["name"],
                              spell["effect"]["duration"])
            result["effect"] = spell["effect"]
    return result
