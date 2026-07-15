from pathlib import Path
from random import Random

from ttrpg_engine import combat, derive, dice, grid, timeline, worldfs
from ttrpg_engine.errors import EngineError


def _sheet(root: Path, actor: str) -> dict:
    return worldfs.read_yaml(worldfs.state(root, f"party/{actor}"))


def add_item(root: Path, g: dict, actor: str, item: str, qty: int) -> dict:
    if qty < 1:
        raise EngineError("bad_qty", f"qty must be >= 1, got {qty}")
    if item not in g["items"]:
        raise EngineError("unknown_item", f"no item {item} in this game")
    sheet = _sheet(root, actor)
    line = next((l for l in sheet["inventory"] if l["item"] == item), None)
    if line:
        line["qty"] += qty
    else:
        sheet["inventory"].append({"item": item, "qty": qty})
    worldfs.write_yaml(worldfs.state(root, f"party/{actor}"), sheet)
    timeline.append_event(root, type_="item", actors=[actor],
                          summary=f"{actor} gains {qty}x {item}")
    return {"actor": actor, "inventory": sheet["inventory"]}


def remove_item(root: Path, g: dict, actor: str, item: str, qty: int) -> dict:
    if qty < 1:
        raise EngineError("bad_qty", f"qty must be >= 1, got {qty}")
    sheet = _sheet(root, actor)
    line = next((l for l in sheet["inventory"] if l["item"] == item), None)
    if line is None or line["qty"] < qty:
        raise EngineError("not_enough", f"{actor} does not have {qty}x {item}")
    if line.get("equipped"):
        raise EngineError("equipped", f"{actor} must unequip {item} before removing it")
    line["qty"] -= qty
    sheet["inventory"] = [l for l in sheet["inventory"] if l["qty"] > 0]
    worldfs.write_yaml(worldfs.state(root, f"party/{actor}"), sheet)
    timeline.append_event(root, type_="item", actors=[actor],
                          summary=f"{actor} loses {qty}x {item}")
    return {"actor": actor, "inventory": sheet["inventory"]}


def adjust_gold(root: Path, target: str, amount: int) -> dict:
    if target == "party":
        data = worldfs.read_yaml(worldfs.state(root, "party"))
    else:
        data = _sheet(root, target)
    if data["gold"] + amount < 0:
        raise EngineError("not_enough", f"{target} has only {data['gold']} gp")
    before = data["gold"]
    data["gold"] += amount
    path = worldfs.state(root, "party" if target == "party" else f"party/{target}")
    worldfs.write_yaml(path, data)
    verb = "gains" if amount >= 0 else "spends"
    timeline.append_event(root, type_="gold", actors=[] if target == "party" else [target],
                          summary=f"{target} {verb} {abs(amount)} gp",
                          delta={target: {"gold": [before, data["gold"]]}})
    return {"target": target, "gold": data["gold"]}


def _find_line(sheet: dict, item: str) -> dict | None:
    return next((l for l in sheet["inventory"] if l["item"] == item), None)


def _still_granted(sheet: dict, g: dict, line: dict, name: str) -> bool:
    """True if some OTHER equipped, non-dispelled item also grants effect `name`."""
    return any(
        other is not line and other.get("equipped") and not other.get("dispelled")
        and g["items"][other["item"]].get("grants_effect", {}).get("name") == name
        for other in sheet["inventory"]
    )


def _check_gear_economy(enc: dict | None, actor: str, spec: dict, force: bool) -> None:
    """Enforce combat action economy for equip/unequip. `--force` (GM override)
    bypasses both the armor block and the one-swap-per-round limit."""
    if force or enc is None or actor not in enc["order"]:
        return
    if spec["type"] == "armor":
        raise EngineError("no_time", "cannot don or doff armor mid-encounter")
    if enc.get("gear_actions", {}).get(actor) == enc["round"]:
        raise EngineError("action_spent", f"{actor} has already swapped gear this round")


def _record_gear_action(enc: dict | None, actor: str, spec: dict) -> bool:
    """Track that `actor` spent this round's gear swap. Armor is never tracked
    here since rule 1 blocks it outright (no allowance to record)."""
    if enc is None or actor not in enc["order"] or spec["type"] == "armor":
        return False
    enc.setdefault("gear_actions", {})[actor] = enc["round"]
    return True


def _require_pc(root: Path, actor: str):
    """Resolve an actor that must be a PC (monsters carry no inventory)."""
    kind, sheet, enc = combat.resolve_actor(root, actor)
    if kind != "pc":
        raise EngineError("not_a_pc", f"{actor} is not a PC; only PCs carry gear")
    return sheet, enc


def equip(root: Path, g: dict, actor: str, item: str, *, force: bool = False) -> dict:
    sheet, enc = _require_pc(root, actor)
    line = _find_line(sheet, item)
    if line is None:
        raise EngineError("not_carried", f"{actor} does not carry {item}")
    spec = g["items"][item]
    _check_gear_economy(enc, actor, spec, force)
    if spec["type"] == "armor" and any(
        other["item"] != item and other.get("equipped") and g["items"][other["item"]]["type"] == "armor"
        for other in sheet["inventory"]
    ):
        raise EngineError("armor_conflict", f"{actor} must unequip current armor before equipping {item}")
    line["equipped"] = True
    grants = spec.get("grants_effect")
    if grants and not line.get("dispelled"):
        name = grants["name"]
        sheet["effects"] = [e for e in sheet["effects"] if e["name"] != name]
        sheet["effects"].append({"name": name, "duration": -1})
    derive.recompute(sheet, g)
    combat.save_pc(root, sheet)
    if _record_gear_action(enc, actor, spec):
        combat.save_encounter(root, enc)
    cursed = bool(spec.get("cursed", False))
    summary = f"{actor} equips {item}" + (" (cursed!)" if cursed else "")
    if force:
        summary += " (forced)"
    timeline.append_event(root, type_="equip", actors=[actor], summary=summary)
    return {"actor": actor, "item": item, "ac": sheet["ac"], "attacks": sheet["attacks"],
            "effects": sheet["effects"], "cursed": cursed, "forced": force}


def unequip(root: Path, g: dict, actor: str, item: str, *, force: bool = False) -> dict:
    sheet, enc = _require_pc(root, actor)
    line = _find_line(sheet, item)
    if line is None:
        raise EngineError("not_carried", f"{actor} does not carry {item}")
    if not line.get("equipped"):
        raise EngineError("not_equipped", f"{actor} does not have {item} equipped")
    spec = g["items"][item]
    _check_gear_economy(enc, actor, spec, force)
    if spec.get("cursed") and not line.get("dispelled"):
        raise EngineError("cursed", f"{item} is cursed; dispel it before unequipping")
    line.pop("equipped", None)
    grants = spec.get("grants_effect")
    if grants and not line.get("dispelled"):
        name = grants["name"]
        if not _still_granted(sheet, g, line, name):
            sheet["effects"] = [e for e in sheet["effects"] if e["name"] != name]
    derive.recompute(sheet, g)
    combat.save_pc(root, sheet)
    if _record_gear_action(enc, actor, spec):
        combat.save_encounter(root, enc)
    summary = f"{actor} unequips {item}"
    if force:
        summary += " (forced)"
    timeline.append_event(root, type_="unequip", actors=[actor], summary=summary)
    return {"actor": actor, "item": item, "ac": sheet["ac"], "attacks": sheet["attacks"],
            "effects": sheet["effects"], "forced": force}


def use(root: Path, g: dict, actor: str, item: str, target: str | None,
        rng: Random, *, force: bool = False) -> dict:
    kind, sheet, enc = combat.resolve_actor(root, actor)
    if kind != "pc":
        raise EngineError("not_pc", "only PCs carry inventory")
    if item not in g["items"]:
        raise EngineError("unknown_item", f"no item {item} in this game")
    spec = g["items"][item]
    if spec.get("type") != "consumable":
        raise EngineError("not_consumable", f"{item} is not a consumable")
    if not any(k in spec for k in ("heal", "damage", "grants_effect")):
        raise EngineError("inert", f"{item} defines no heal, damage, or grants_effect")
    line = _find_line(sheet, item)
    if line is None:
        raise EngineError("not_carried", f"{actor} does not carry {item}")
    target = target or actor
    if target != actor:
        combat.resolve_actor(root, target)  # must exist
        if enc and actor in enc["positions"] and target in enc["positions"]:
            dist = grid.chebyshev(tuple(enc["positions"][actor]),
                                  tuple(enc["positions"][target]))
            if dist > 1:
                raise EngineError("out_of_range", f"{target} is {dist} away, must be adjacent")
            if not combat.same_plane(enc, actor, target):
                raise EngineError("unreachable", f"{actor} and {target} are not on the same plane")
    _check_gear_economy(enc, actor, spec, force)
    # spend the item before resolving, mirroring spell-slot spending
    line["qty"] -= 1
    sheet["inventory"] = [l for l in sheet["inventory"] if l["qty"] > 0]
    combat.save_pc(root, sheet)
    if _record_gear_action(enc, actor, spec):
        combat.save_encounter(root, enc)
    timeline.append_event(root, type_="item", actors=[actor, target],
                          summary=f"{actor} uses {item}"
                                  + (f" on {target}" if target != actor else ""))
    result = {"actor": actor, "item": item, "target": target,
              "qty_left": max(0, line["qty"]), "forced": force}
    if "heal" in spec:
        amount = dice.roll(str(spec["heal"]), rng).total
        result["healed"] = combat.apply_heal(root, target, amount,
                                             source=f"{actor}:{item}")["amount"]
    if "damage" in spec:
        dmg = dice.roll(str(spec["damage"]), rng).total
        result["damage"] = combat.apply_damage(root, target, dmg,
                                               source=f"{actor}:{item}", rng=rng)["amount"]
    if "grants_effect" in spec:
        eff = spec["grants_effect"]
        combat.set_effect(root, target, eff["name"], eff.get("duration", -1))
        result["effect"] = eff
    return result


def dispel(root: Path, g: dict, actor: str, item: str) -> dict:
    sheet = _sheet(root, actor)
    line = _find_line(sheet, item)
    if line is None:
        raise EngineError("not_carried", f"{actor} does not carry {item}")
    if not line.get("equipped"):
        raise EngineError("not_equipped", f"{actor} does not have {item} equipped")
    if not line.get("dispelled"):
        line["dispelled"] = True
        grants = g["items"][item].get("grants_effect")
        if grants:
            name = grants["name"]
            if not _still_granted(sheet, g, line, name):
                sheet["effects"] = [e for e in sheet["effects"] if e["name"] != name]
        worldfs.write_yaml(worldfs.state(root, f"party/{actor}"), sheet)
        timeline.append_event(root, type_="dispel", actors=[actor],
                              summary=f"{actor} dispels the curse on {item}")
    return {"actor": actor, "item": item, "effects": sheet["effects"]}
