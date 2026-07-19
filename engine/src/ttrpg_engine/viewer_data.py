import copy
import re
from pathlib import Path

from ttrpg_engine import game as game_mod
from ttrpg_engine import quests, region_map, render, worldfs
from ttrpg_engine.combat import effect_names
from ttrpg_engine.errors import EngineError
from ttrpg_engine.markdown_render import render_markdown, sanitize_html

# authored SVG art is canon content run through the same sanitizer as
# markdown, plus a foreignObject strip (it can smuggle arbitrary HTML)
_FOREIGN_RE = re.compile(r"<foreignObject\b.*?</foreignObject>",
                         re.DOTALL | re.IGNORECASE)


def _art_svg(root: Path, ref: str) -> str | None:
    p = root / "canon" / "art" / f"{ref}.svg"
    if not p.is_file():
        return None
    return _FOREIGN_RE.sub("", sanitize_html(p.read_text()))

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
                     "wounds": mon.get("wounds", []),
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
                     "effects": names, "wounds": sheet.get("wounds", []),
                     "aloft": aloft, "dead": "dead" in names,
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


def _quests(root: Path, lens: str, at_location: str | None) -> list[dict]:
    # raw file reads only — quests.list_quests/visible_quests expire overdue
    # quests on disk as a side effect, and the viewer must never write anything.
    # We apply the same player-lens visibility rule (reveal-on-arrival) as
    # quests.visible_quests, but against the raw reads.
    qdir = root / "state" / "quests"
    if not qdir.is_dir():
        return []
    out = [worldfs.read_yaml(p) for p in sorted(qdir.glob("*.yaml"))]
    if lens != "gm":
        out = [q for q in out if quests.is_visible(q, at_location)]
    return out


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

def _pc_card(root: Path, ref: str, g: dict | None = None) -> dict:
    sheet = worldfs.read_yaml(worldfs.state(root, f"party/{ref}"))
    bio = root / "canon" / "party" / f"{ref}.md"
    spells_known = sheet.get("spells_known", [])
    # each known spell's level, resolved from the ruleset when we have it, so the
    # sheet can group cantrips (level 0) apart from leveled spells and the chips
    # can deep-link to a spell card. Missing/unknown spells simply omit a level.
    spell_defs = (g or {}).get("spells", {})
    spells = [{"name": s, "level": spell_defs.get(s, {}).get("level")}
              for s in spells_known]
    return {
        "kind": "pc", "id": ref, "name": sheet["name"],
        "race": sheet["race"], "class": sheet["class"], "level": sheet["level"],
        "xp": sheet["xp"], "hp": sheet["hp"], "max_hp": sheet["max_hp"],
        "ac": sheet["ac"], "speed": sheet["speed"],
        "played_by": sheet.get("played_by"),
        "attributes": sheet["attributes"], "skills": sheet["skills"],
        "effects": [e["name"] for e in sheet.get("effects", [])],
        "wounds": sheet.get("wounds", []),
        "features": sheet.get("features", []),
        "spells_known": spells_known,
        "spells": spells,
        "spell_slots": sheet.get("spell_slots") or None,
        # the full carried inventory, not just what's equipped — the operator
        # needs to see the shortbow/torches/rope they just bought
        "inventory": [{"item": l["item"], "qty": l.get("qty", 1),
                       "equipped": bool(l.get("equipped"))}
                      for l in sheet.get("inventory", [])],
        "equipped": [l["item"] for l in sheet.get("inventory", []) if l.get("equipped")],
        "gold": sheet.get("gold", 0),
        "bio_html": render_markdown(bio.read_text()) if bio.exists() else None,
    }


def _spell_card(g: dict, name: str) -> dict:
    """A spell definition as a card. Spell data is player-safe (no GM-only
    fields), so the same card serves both lenses."""
    spell = (g or {}).get("spells", {}).get(name)
    if spell is None:
        raise EngineError("not_found", f"no spell {name!r}")
    return {
        "kind": "spell", "id": f"spell:{name}", "spell_name": name,
        "name": name.replace("_", " ").title(),
        "level": spell.get("level", 0),
        "action": spell.get("action"),
        "range": spell.get("range"),
        "resolve": spell.get("resolve"),
        "save_attr": spell.get("save_attr"),
        "on_save": spell.get("on_save"),
        "damage": spell.get("damage"),
        "heal": spell.get("heal"),
        "area": spell.get("area"),
        "effect": spell.get("effect"),
        "description": " ".join(str(spell.get("description", "")).split()) or None,
    }


def _content_art_path(g: dict, rel) -> str | None:
    """Return the content-relative art path `rel` iff it is a non-empty string
    AND the file exists under the game's content dir; otherwise None (fail open).
    A missing value, missing content dir, or missing file all degrade to None
    rather than raising — art is always optional. The viewer serves the resolved
    path under its guarded `/art/` route."""
    content = g.get("content_dir")
    if not (content is not None and isinstance(rel, str) and rel):
        return None
    try:
        return rel if (Path(content) / rel).exists() else None
    except OSError:
        return None


def _monster_image(g: dict, entry: dict) -> str | None:
    """A bestiary entry's portrait path, failing open — no monster is required
    to have art. See _content_art_path."""
    return _content_art_path(g, entry.get("image") if isinstance(entry, dict) else None)


def _monster_instance_card(g: dict, enc: dict, ref: str, lens: str) -> dict:
    mon = enc["monsters"][ref]
    if lens != "gm" and "hidden" in effect_names(mon):
        raise EngineError("not_found", f"no entity {ref!r}")   # don't leak existence
    try:
        entry = game_mod.bestiary_entry(g, mon["type"])
    except EngineError:
        entry = {}
    desc = entry.get("description", "")
    card = {"kind": "monster", "id": ref, "name": mon["name"],
            "type": mon.get("type"), "description": " ".join(str(desc).split()),
            "image": _monster_image(g, entry),
            "effects": [e["name"] for e in mon.get("effects", [])],
            # wounds are physical/observable — player-safe even for foes
            "wounds": mon.get("wounds", []),
            "aloft": bool(enc.get("aloft", {}).get(ref)),
            "dead": bool(mon.get("dead"))}
    if lens == "gm":
        card.update(hp=mon["hp"], max_hp=mon["max_hp"], ac=mon.get("ac"),
                    attributes=mon.get("attributes"), attacks=mon.get("attacks"),
                    xp=mon.get("xp"))
    else:
        card["status"] = _monster_status(mon)
    return card


def _monster_type_card(g: dict, entry: dict, ref: str, lens: str) -> dict:
    card = {"kind": "monster", "id": ref,
            "name": entry.get("name", ref),
            "description": " ".join(str(entry.get("description", "")).split()),
            "image": _monster_image(g, entry)}
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


def _shop_card(root: Path, g: dict, npc_id: str, lens: str) -> dict:
    """A merchant's wares as a card. Stock is the NPC's `stock` list (falling
    back to whatever they physically hold in `inventory`); each line is joined
    to the pinned game's items for its list price, type, and description, so
    price stays single-sourced in ruleset/items.yaml and never drifts. Prices
    are public, so one card serves both lenses — only the merchant's own purse
    (what they can pay when buying from the party) is GM-only."""
    npcs_path = root / "canon" / "npcs.yaml"
    npcs = worldfs.read_yaml(npcs_path) if npcs_path.exists() else {}
    npc = npcs.get(npc_id)
    if npc is None:
        raise EngineError("not_found", f"no NPC {npc_id!r} in canon/npcs.yaml")
    items = g.get("items", {})
    raw = npc.get("stock") or npc.get("inventory") or []
    goods = []
    for line in raw:
        iid = line if isinstance(line, str) else line.get("item")
        if not iid:
            continue
        idef = items.get(iid) or {}
        goods.append({
            "item": iid,
            "name": iid.replace("_", " ").title(),
            "qty": 1 if isinstance(line, str) else line.get("qty", 1),
            "price": idef.get("price"),
            "type": idef.get("type"),
            "description": " ".join(str(idef.get("description", "")).split()) or None,
            "known": bool(idef),   # false = stock line with no matching item def
        })
    card = {"kind": "shop", "id": f"shop:{npc_id}", "merchant_id": npc_id,
            "name": f"{npc.get('name', npc_id)} — wares",
            "merchant": npc.get("name", npc_id),
            "location": npc.get("location"),
            "items": goods}
    if lens == "gm":
        card["gold"] = npc.get("gold")   # the merchant's purse (GM-only)
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


def _location_card(root: Path, g: dict, region: dict, ref: str, lens: str) -> dict:
    """A region node as a card: description, ways out, authored art. Player
    lens honors the fog — a merely-rumored node shows its name and nothing
    more, an unknown one doesn't resolve at all."""
    node = region["nodes"][ref]
    vis = region_map.visited_nodes(root, g)
    if lens != "gm" and ref not in vis:
        neighbours = {b if a == ref else a
                      for e in region.get("edges", [])
                      for a, b in [e["between"]] if ref in (a, b)}
        if neighbours & vis:
            return {"kind": "location", "id": ref, "name": node.get("name", ref),
                    "terrain": node.get("terrain"), "rumored": True}
        raise EngineError("not_found", f"no entity {ref!r}")
    party = worldfs.read_yaml(worldfs.state(root, "party"))
    card = {"kind": "location", "id": ref, "name": node.get("name", ref),
            "terrain": node.get("terrain"),
            "description": " ".join(str(node.get("description", "")).split()) or None,
            "visited": ref in vis,
            "party_here": str(party["location"]) == ref,
            "connections": [
                {"id": other, "name": region["nodes"].get(other, {}).get("name", other),
                 "hours": e["hours"]}
                for e in region.get("edges", [])
                for a, b in [e["between"]] if ref in (a, b)
                for other in [b if a == ref else a]
            ],
            "art_svg": _art_svg(root, ref),
            "banner": _content_art_path(g, node.get("banner"))}
    if lens == "gm":
        npcs_path = root / "canon" / "npcs.yaml"
        npcs = worldfs.read_yaml(npcs_path) if npcs_path.exists() else {}
        card["npcs"] = [{"id": nid, "name": n.get("name", nid), "role": n.get("role")}
                        for nid, n in npcs.items() if n.get("location") == ref]
    return card


def entity_card(root: Path, g: dict, ref: str, lens: str) -> dict:
    """Resolve `ref` — a PC id, an encounter combatant, a bestiary type, an
    NPC key from canon/npcs.yaml, a quest id, or a region node — into a
    lens-aware card of its live state. Raises not_found for anything unknown,
    including monsters and locations a player lens isn't allowed to see."""
    lens = "gm" if lens == "gm" else "player"
    if ref.startswith("spell:"):
        return _spell_card(g, ref.removeprefix("spell:"))
    if ref.startswith("shop:"):
        return _shop_card(root, g, ref.removeprefix("shop:"), lens)
    if ref.startswith("pc-"):
        if worldfs.state(root, f"party/{ref}").exists():
            return _pc_card(root, ref, g)
        raise EngineError("not_found", f"no entity {ref!r}")
    if (root / "state" / "encounter.yaml").exists():
        enc = render.load_encounter(root)
        if ref in enc["monsters"]:
            return _monster_instance_card(g, enc, ref, lens)
    bestiary = game_mod.bestiary(g)
    if ref in bestiary:
        return _monster_type_card(g, bestiary[ref], ref, lens)
    npcs_path = root / "canon" / "npcs.yaml"
    if npcs_path.exists():
        npcs = worldfs.read_yaml(npcs_path)
        if ref in npcs:
            return _npc_card(npcs[ref], ref, lens)
    quest_path = root / "state" / "quests" / f"{ref}.yaml"
    if quest_path.exists():
        return _quest_card(worldfs.read_yaml(quest_path), lens)
    region_path = root / "canon" / "maps" / "region.yaml"
    if region_path.exists():
        region = worldfs.read_yaml(region_path)
        if ref in region.get("nodes", {}):
            return _location_card(root, g, region, ref, lens)
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
        "quests": _quests(root, lens, str(party["location"])),
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
                             "roster": roster, "legend": legend,
                             "terrain_legend": render.terrain_legend(view)}
        # a hidden monster's turn passes up="???" (no real cid) -> no highlight
        snap["map_svg"] = render.svg_map(
            view, caption=False, status=_token_status(roster),
            up=up if up != "???" else None)
    elif (root / "canon" / "maps" / "region.yaml").exists():
        # no fight running: the map pane shows the world instead of a void
        try:
            snap["region_svg"] = region_map.svg(root, g, lens)
        except Exception:
            snap["region_svg"] = None   # a malformed region must not kill the viewer
    if lens == "gm":
        snap["internals"] = {k: (enc or {}).get(k) or {} for k in _INTERNAL_KEYS}
        snap["timeline"] = _timeline_tail(root)
    return snap
