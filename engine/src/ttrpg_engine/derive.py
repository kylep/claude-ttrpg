"""Derives computed sheet stats (AC, attacks) from currently-equipped gear."""


def attr_mod(score: int) -> int:
    return (score - 10) // 2


def _equipped_items(sheet: dict) -> list[str]:
    return [l["item"] for l in sheet["inventory"] if l.get("equipped")]


def armor_class(g: dict, equipped: list[str], dex: int) -> int:
    for item in equipped:
        spec = g["items"][item]
        if spec["type"] == "armor":
            ac = spec["ac_base"] + (attr_mod(dex) if spec["add_dex"] else 0)
            ac += spec.get("bonus", {}).get("ac", 0)
            return ac
    return 10 + attr_mod(dex)


def attacks(g: dict, equipped: list[str], attrs: dict, prof: int) -> list[dict]:
    out = []
    for item in equipped:
        spec = g["items"][item]
        if spec["type"] != "weapon":
            continue
        use_dex = spec["finesse"] and attrs["DEX"] >= attrs["STR"]
        mod = attr_mod(attrs["DEX" if use_dex else "STR"])
        bonus = spec.get("bonus", {})
        dmg_mod = mod + bonus.get("damage", 0)
        dmg = spec["damage"] + (f"{dmg_mod:+d}" if dmg_mod else "")
        out.append({"name": item, "attack_mod": mod + prof + bonus.get("attack", 0),
                    "damage": dmg, "range": spec["range"]})
    return out


def recompute(sheet: dict, g: dict) -> dict:
    """Set sheet['ac'] and sheet['attacks'] from currently-equipped inventory lines."""
    equipped = _equipped_items(sheet)
    sheet["ac"] = armor_class(g, equipped, sheet["attributes"]["DEX"])
    sheet["attacks"] = attacks(g, equipped, sheet["attributes"], sheet["proficiency"])
    return sheet


def equipment_effects(sheet: dict, g: dict) -> list[dict]:
    """Effects granted by currently-equipped, non-dispelled inventory lines.

    Deduplicated by effect name (several items may grant the same effect).
    """
    out: dict[str, dict] = {}
    for line in sheet["inventory"]:
        if not line.get("equipped") or line.get("dispelled"):
            continue
        grants = g["items"][line["item"]].get("grants_effect")
        if grants:
            out[grants["name"]] = {"name": grants["name"], "duration": -1}
    return list(out.values())
