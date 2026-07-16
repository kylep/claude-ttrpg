import copy
from pathlib import Path

from ttrpg_engine import game as game_mod
from ttrpg_engine import render, worldfs
from ttrpg_engine.combat import effect_names
from ttrpg_engine.errors import EngineError
from ttrpg_engine.markdown_render import render_markdown

_TIMELINE_TAIL = 30  # how many recent timeline events the GM lens shows
# encounter bookkeeping surfaced only in the GM lens, never to players
_INTERNAL_KEYS = ("stealth", "grapples", "sneak_used", "gear_actions", "aloft")
# coarse health bands for a monster the players only see as a status word — the
# token ring then matches the healthy/wounded/bloodied word they already have
_BAND_FRAC = {"healthy": 0.8, "wounded": 0.5, "bloodied": 0.2, "down": 0.0}


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
                entry["ac"] = mon.get("ac")   # AC stays GM-only for foes
            else:
                entry["status"] = _monster_status(mon)
        else:
            sheet = worldfs.read_yaml(worldfs.state(root, f"party/{cid}"))
            names = [e["name"] for e in sheet.get("effects", [])]
            entry = {"id": cid, "name": sheet["name"], "side": "pc",
                     "effects": names, "aloft": aloft, "dead": "dead" in names,
                     "hp": sheet["hp"], "max_hp": sheet["max_hp"],
                     "ac": sheet.get("ac")}
        entries.append(entry)
    return entries


def _token_status(roster: list[dict]) -> dict:
    """Overlay for render.svg_map so PC tokens (and player-lens monsters, seen
    only as a word) get health rings and condition pips too."""
    out = {}
    for r in roster:
        if "hp" in r and r.get("max_hp"):
            frac = r["hp"] / r["max_hp"]
        else:
            frac = _BAND_FRAC.get(r.get("status"))
        names = set(r.get("effects", []))
        out[r["id"]] = {
            "hp_frac": None if r.get("dead") else frac,
            "dead": bool(r.get("dead")),
            "hidden": "hidden" in names,
            "bad": bool(names & render._BAD_EFFECTS),
            "aloft": bool(r.get("aloft")),
        }
    return out


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


# --- entity cards -----------------------------------------------------------
#
# One resolver for everything a feed card or a roster click can reference.
# Cards read live state at request time, so an open card is always current.

def _pc_card(root: Path, ref: str) -> dict:
    sheet = worldfs.read_yaml(worldfs.state(root, f"party/{ref}"))
    bio = root / "canon" / "party" / f"{ref}.md"
    return {
        "kind": "pc", "id": ref, "name": sheet["name"],
        "race": sheet["race"], "class": sheet["class"], "level": sheet["level"],
        "xp": sheet["xp"], "hp": sheet["hp"], "max_hp": sheet["max_hp"],
        "ac": sheet["ac"], "speed": sheet["speed"],
        "played_by": sheet.get("played_by"),
        "attributes": sheet["attributes"], "skills": sheet["skills"],
        "effects": [e["name"] for e in sheet.get("effects", [])],
        "features": sheet.get("features", []),
        "spells_known": sheet.get("spells_known", []),
        "equipped": [l["item"] for l in sheet.get("inventory", []) if l.get("equipped")],
        "gold": sheet.get("gold", 0),
        "bio_html": render_markdown(bio.read_text()) if bio.exists() else None,
    }


def _monster_instance_card(g: dict, enc: dict, ref: str, lens: str) -> dict:
    mon = enc["monsters"][ref]
    if lens != "gm" and "hidden" in effect_names(mon):
        raise EngineError("not_found", f"no entity {ref!r}")   # don't leak existence
    try:
        desc = game_mod.bestiary_entry(g, mon["type"]).get("description", "")
    except EngineError:
        desc = ""
    card = {"kind": "monster", "id": ref, "name": mon["name"],
            "type": mon.get("type"), "description": " ".join(str(desc).split()),
            "effects": [e["name"] for e in mon.get("effects", [])],
            "aloft": bool(enc.get("aloft", {}).get(ref)),
            "dead": bool(mon.get("dead"))}
    if lens == "gm":
        card.update(hp=mon["hp"], max_hp=mon["max_hp"], ac=mon.get("ac"),
                    attributes=mon.get("attributes"), attacks=mon.get("attacks"),
                    xp=mon.get("xp"))
    else:
        card["status"] = _monster_status(mon)
    return card


def _monster_type_card(entry: dict, ref: str, lens: str) -> dict:
    card = {"kind": "monster", "id": ref,
            "name": entry.get("name", ref),
            "description": " ".join(str(entry.get("description", "")).split())}
    if lens == "gm":
        card.update(hp=entry.get("hp"), max_hp=entry.get("hp"), ac=entry.get("ac"),
                    speed=entry.get("speed"), attributes=entry.get("attributes"),
                    attacks=entry.get("attacks"), xp=entry.get("xp"),
                    notes=" ".join(str(entry.get("notes", "")).split()) or None)
    return card


def _npc_card(npc: dict, ref: str, lens: str) -> dict:
    card = {"kind": "npc", "id": ref, "name": npc.get("name", ref),
            "role": npc.get("role"), "disposition": npc.get("disposition"),
            "location": npc.get("location"),
            "description": " ".join(str(npc.get("description", "")).split()) or None}
    if lens == "gm":
        card["wants"] = " ".join(str(npc.get("wants", "")).split()) or None
    return card


def _quest_card(quest: dict, lens: str) -> dict:
    card = {"kind": "quest", "id": quest["id"], "name": quest["title"],
            "status": quest["status"], "description": quest.get("description"),
            "giver": quest.get("giver"), "deadline": quest.get("deadline"),
            "accepted_by": quest.get("accepted_by", []),
            "reward": quest.get("reward")}
    if lens == "gm":
        card["escrow"] = quest.get("escrow")
        card["escrow_from"] = quest.get("escrow_from")
    return card


def entity_card(root: Path, g: dict, ref: str, lens: str) -> dict:
    """Resolve `ref` — a PC id, an encounter combatant, a bestiary type, an
    NPC key from canon/npcs.yaml, or a quest id — into a lens-aware card of
    its live state. Raises not_found for anything unknown, including monsters
    a player lens isn't allowed to see."""
    lens = "gm" if lens == "gm" else "player"
    if ref.startswith("pc-"):
        if worldfs.state(root, f"party/{ref}").exists():
            return _pc_card(root, ref)
        raise EngineError("not_found", f"no entity {ref!r}")
    if (root / "state" / "encounter.yaml").exists():
        enc = render.load_encounter(root)
        if ref in enc["monsters"]:
            return _monster_instance_card(g, enc, ref, lens)
    bestiary = game_mod.bestiary(g)
    if ref in bestiary:
        return _monster_type_card(bestiary[ref], ref, lens)
    npcs_path = root / "canon" / "npcs.yaml"
    if npcs_path.exists():
        npcs = worldfs.read_yaml(npcs_path)
        if ref in npcs:
            return _npc_card(npcs[ref], ref, lens)
    quest_path = root / "state" / "quests" / f"{ref}.yaml"
    if quest_path.exists():
        return _quest_card(worldfs.read_yaml(quest_path), lens)
    raise EngineError("not_found", f"no entity {ref!r}")


def state_snapshot(root: Path, g: dict, lens: str) -> dict:
    lens = "gm" if lens == "gm" else "player"
    party = worldfs.read_yaml(worldfs.state(root, "party"))
    snap = {
        "lens": lens,
        "world": worldfs.read_yaml(root / "world.yaml")["world"],
        "clock": worldfs.read_yaml(worldfs.state(root, "clock")),
        "location": str(party["location"]).replace("-", " ").replace("_", " ").title(),
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
        roster = _roster(root, enc, view, lens)
        syms = render.symbols(view)
        legend = [{"id": r["id"], "sym": syms[r["id"]], "name": r["name"],
                   "side": r["side"]} for r in roster if r["id"] in syms]
        snap["encounter"] = {"id": enc["id"], "name": enc["name"],
                             "round": enc["round"], "up": up,
                             "roster": roster, "legend": legend}
        # a hidden monster's turn passes up="???" (no real cid) -> no highlight
        snap["map_svg"] = render.svg_map(
            view, caption=False, status=_token_status(roster),
            up=up if up != "???" else None)
    if lens == "gm":
        snap["internals"] = {k: (enc or {}).get(k) or {} for k in _INTERNAL_KEYS}
        snap["timeline"] = _timeline_tail(root)
    return snap
