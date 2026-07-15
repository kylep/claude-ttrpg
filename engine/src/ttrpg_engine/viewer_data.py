import copy
from pathlib import Path

from ttrpg_engine import render, worldfs
from ttrpg_engine.combat import effect_names

_TIMELINE_TAIL = 30
_INTERNAL_KEYS = ("stealth", "grapples", "sneak_used", "gear_actions", "aloft")


def player_encounter(enc: dict) -> dict:
    """Deep-copied encounter safe to show players: monsters carrying `hidden`
    are gone from tokens, legend, and turn order; GM bookkeeping keys dropped.
    Hidden PCs pass through — the players know where their own rogue is."""
    out = copy.deepcopy(enc)
    hidden = {cid for cid, m in enc["monsters"].items() if "hidden" in effect_names(m)}
    for cid in hidden:
        del out["monsters"][cid]
        out["positions"].pop(cid, None)
    out["order"] = [cid for cid in out["order"] if cid not in hidden]
    for key in ("stealth", "grapples", "sneak_used", "gear_actions"):
        out.pop(key, None)
    return out


def _monster_status(mon: dict) -> str:
    if mon.get("dead"):
        return "down"
    frac = mon["hp"] / mon["max_hp"]
    if frac > 2 / 3:
        return "healthy"
    if frac > 1 / 3:
        return "wounded"
    return "bloodied"


def _roster(root: Path, enc: dict, view: dict, lens: str) -> list[dict]:
    entries = []
    for cid in view["order"]:
        aloft = bool(enc.get("aloft", {}).get(cid))
        if cid in enc["monsters"]:
            mon = enc["monsters"][cid]
            entry = {"id": cid, "name": mon["name"], "side": "monster",
                     "effects": [e["name"] for e in mon.get("effects", [])],
                     "aloft": aloft, "dead": bool(mon.get("dead"))}
            if lens == "gm":
                entry["hp"] = mon["hp"]
                entry["max_hp"] = mon["max_hp"]
            else:
                entry["status"] = _monster_status(mon)
        else:
            sheet = worldfs.read_yaml(worldfs.state(root, f"party/{cid}"))
            names = [e["name"] for e in sheet.get("effects", [])]
            entry = {"id": cid, "name": sheet["name"], "side": "pc",
                     "effects": names, "aloft": aloft, "dead": "dead" in names,
                     "hp": sheet["hp"], "max_hp": sheet["max_hp"]}
        entries.append(entry)
    return entries


def _quests(root: Path) -> list[dict]:
    # raw file reads only — quests.list_quests expires overdue quests on
    # disk as a side effect, and the viewer must never write anything
    qdir = root / "state" / "quests"
    if not qdir.is_dir():
        return []
    return [worldfs.read_yaml(p) for p in sorted(qdir.glob("*.yaml"))]


def _timeline_tail(root: Path) -> list[dict]:
    out = []
    for p in sorted((root / "timeline").glob("*.yaml"))[-_TIMELINE_TAIL:]:
        ev = worldfs.read_yaml(p)
        out.append({"id": p.stem, "type": ev.get("type"), "summary": ev.get("summary")})
    return out


def state_snapshot(root: Path, g: dict, lens: str) -> dict:
    lens = "gm" if lens == "gm" else "player"
    party = worldfs.read_yaml(worldfs.state(root, "party"))
    snap = {
        "lens": lens,
        "world": worldfs.read_yaml(root / "world.yaml")["world"],
        "clock": worldfs.read_yaml(worldfs.state(root, "clock")),
        "location": party["location"],
        "party_gold": party["gold"],
        "stash": party["stash"],
        "party": [worldfs.read_yaml(worldfs.state(root, f"party/{pid}"))
                  for pid in party["members"]],
        "quests": _quests(root),
        "encounter": None,
        "map_svg": None,
    }
    enc = None
    if (root / "state" / "encounter.yaml").exists():
        enc = render.load_encounter(root)
        view = enc if lens == "gm" else player_encounter(enc)
        up = enc["order"][enc["turn"]]
        if up not in view["order"]:
            up = "???"  # a hidden monster's turn must not name it to players
        snap["encounter"] = {"id": enc["id"], "name": enc["name"],
                             "round": enc["round"], "up": up,
                             "roster": _roster(root, enc, view, lens)}
        snap["map_svg"] = render.svg_map(view)
    if lens == "gm":
        snap["internals"] = {k: (enc or {}).get(k) or {} for k in _INTERNAL_KEYS}
        snap["timeline"] = _timeline_tail(root)
    return snap
