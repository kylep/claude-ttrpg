from collections import Counter
from pathlib import Path

from ttrpg_engine import clock as clock_mod
from ttrpg_engine import derive, level as level_mod, story_log, timeline, worldfs
from ttrpg_engine.chargen import slugify
from ttrpg_engine.errors import EngineError

_ACTIVE_STATUSES = {"offered", "accepted"}


def parse_ref(spec: str, *, allow_world: bool = True) -> tuple[str, str | None]:
    """Parse an actor reference: 'npc:ID', 'pc:ID', or 'world' -> (type, id)."""
    if spec == "world":
        if not allow_world:
            raise EngineError("bad_ref", "world cannot hold escrow")
        return "world", None
    kind, _, ident = spec.partition(":")
    if kind not in ("npc", "pc") or not ident:
        raise EngineError("bad_ref", f"bad actor reference {spec!r} (want npc:ID, pc:ID, or world)")
    return kind, ident


# --- NPC holdings (state/npcs.yaml, lazily seeded from canon/npcs.yaml) ---

def _canon_npcs(root: Path) -> dict:
    path = root / "canon" / "npcs.yaml"
    return worldfs.read_yaml(path) if path.exists() else {}


def load_npcs_state(root: Path) -> dict:
    path = worldfs.state(root, "npcs")
    return worldfs.read_yaml(path) if path.exists() else {}


def save_npcs_state(root: Path, data: dict) -> None:
    worldfs.write_yaml(worldfs.state(root, "npcs"), data)


def npc_holdings(root: Path, npcs_state: dict, npc_id: str) -> dict:
    """Return npc_id's holdings dict (a reference into npcs_state), lazily
    seeding it from canon/npcs.yaml's optional gold/inventory fields the
    first time this NPC is accessed. Unknown npc id -> unknown_npc."""
    if npc_id not in npcs_state:
        canon = _canon_npcs(root)
        if npc_id not in canon:
            raise EngineError("unknown_npc", f"no such NPC {npc_id}")
        entry = canon[npc_id]
        npcs_state[npc_id] = {
            "gold": entry.get("gold", 0),
            "inventory": [dict(line) for line in entry.get("inventory", [])],
        }
    return npcs_state[npc_id]


def load_holder(root: Path, kind: str, ident: str) -> tuple[dict, dict | None]:
    """Return (holder, npcs_state) for a pc or npc holder. `npcs_state` is the
    full state/npcs.yaml payload (needed to persist changes) or None for pcs."""
    if kind == "pc":
        path = worldfs.state(root, f"party/{ident}")
        if not path.exists():
            raise EngineError("not_found", f"no such PC {ident}")
        return worldfs.read_yaml(path), None
    if kind == "npc":
        npcs_state = load_npcs_state(root)
        return npc_holdings(root, npcs_state, ident), npcs_state
    raise EngineError("bad_ref", f"cannot hold escrow: {kind}")


def save_holder(root: Path, kind: str, ident: str, holder: dict, npcs_state: dict | None) -> None:
    if kind == "pc":
        worldfs.write_yaml(worldfs.state(root, f"party/{ident}"), holder)
    else:
        save_npcs_state(root, npcs_state)


def _deduct_for_escrow(holder: dict, gold: int, items: list[str], who: str) -> None:
    """Validate then deduct gold/items from `holder` into escrow. Atomic: all
    checks run before any mutation. Each repeated item name in `items` needs
    a separate unit (qty) on the holder; an equipped line can't be escrowed."""
    if gold and holder.get("gold", 0) < gold:
        raise EngineError("not_enough", f"{who} has only {holder.get('gold', 0)} gp")
    counts = Counter(items)
    for item, need in counts.items():
        line = next((l for l in holder["inventory"] if l["item"] == item), None)
        have = line["qty"] if line else 0
        if have < need:
            raise EngineError("not_carried", f"{who} does not carry {need}x {item}")
        if line.get("equipped"):
            raise EngineError("equipped", f"{who} must unequip {item} before it can be escrowed")
    holder["gold"] = holder.get("gold", 0) - gold
    for item, need in counts.items():
        line = next(l for l in holder["inventory"] if l["item"] == item)
        line["qty"] -= need
    holder["inventory"] = [l for l in holder["inventory"] if l["qty"] > 0]


def _refund_to(holder: dict, gold: int, items: list[str]) -> None:
    holder["gold"] = holder.get("gold", 0) + gold
    for item in items:
        line = next((l for l in holder["inventory"] if l["item"] == item), None)
        if line:
            line["qty"] += 1
        else:
            holder["inventory"].append({"item": item, "qty": 1})


def _pay_to_pc(root: Path, pc_id: str, gold: int, items: list[str]) -> None:
    sheet = worldfs.read_yaml(worldfs.state(root, f"party/{pc_id}"))
    _refund_to(sheet, gold, items)
    worldfs.write_yaml(worldfs.state(root, f"party/{pc_id}"), sheet)


# --- quest file storage ---------------------------------------------------

def _quest_path(root: Path, quest_id: str) -> Path:
    return root / "state" / "quests" / f"{quest_id}.yaml"


def load_quest(root: Path, quest_id: str) -> dict:
    path = _quest_path(root, quest_id)
    if not path.exists():
        raise EngineError("not_found", f"no such quest {quest_id}")
    return worldfs.read_yaml(path)


def save_quest(root: Path, quest: dict) -> None:
    worldfs.write_yaml(_quest_path(root, quest["id"]), quest)


def list_quest_ids(root: Path) -> list[str]:
    qdir = root / "state" / "quests"
    if not qdir.is_dir():
        return []
    return sorted(p.stem for p in qdir.glob("*.yaml"))


# --- expiry ---------------------------------------------------------------

def _now_hours(root: Path) -> int:
    clk = worldfs.read_yaml(worldfs.state(root, "clock"))
    return clock_mod.to_hours(clk["date"], clk["hour"])


def _refund_escrow(root: Path, quest: dict) -> None:
    escrow = quest["escrow"]
    ef = quest.get("escrow_from")
    if ef is None or (not escrow["gold"] and not escrow["items"]):
        return
    holder, npcs_state = load_holder(root, ef["type"], ef["id"])
    _refund_to(holder, escrow["gold"], escrow["items"])
    save_holder(root, ef["type"], ef["id"], holder, npcs_state)
    quest["escrow"] = {"gold": 0, "items": []}


def check_expiry(root: Path, quest: dict) -> dict:
    """If `quest` is offered/accepted and its deadline has passed, expire it
    (refund escrow, append an event, persist) and return the updated quest.
    Otherwise return it unchanged. Indefinite quests (deadline None) never
    expire."""
    if quest["status"] not in _ACTIVE_STATUSES or quest["deadline"] is None:
        return quest
    deadline_h = clock_mod.to_hours(quest["deadline"]["date"], quest["deadline"]["hour"])
    if _now_hours(root) < deadline_h:
        return quest
    _refund_escrow(root, quest)
    quest["status"] = "expired"
    save_quest(root, quest)
    timeline.append_event(root, type_="quest", actors=[],
                          summary=f"quest expired: {quest['title']} ({quest['id']})")
    return quest


# --- commands ---------------------------------------------------------------

def offer(root: Path, g: dict, *, title: str, description: str,
          giver_type: str, giver_id: str | None,
          gold: int = 0, items: list[str] | None = None, xp: int = 0,
          deadline: dict | None = None, spawn: bool = False,
          escrow_from_type: str | None = None, escrow_from_id: str | None = None,
          location: str | None = None) -> dict:
    """Create and persist a new 'offered' quest. Funding rules: world quests
    either --spawn rewards from nothing (items validated against the game) or
    escrow them from a holder; NPC/PC quests always escrow from the giver and
    cannot grant xp. Escrowed gold/items are deducted from the holder up front."""
    items = list(items or [])
    if gold < 0:
        raise EngineError("bad_amount", "gold cannot be negative")
    quest_id = slugify(title)
    if not quest_id:
        raise EngineError("bad_title", "title must contain at least one alphanumeric character")
    if _quest_path(root, quest_id).exists():
        raise EngineError("exists", f"quest {quest_id} already exists")

    clk = worldfs.read_yaml(worldfs.state(root, "clock"))
    if deadline is not None:
        now_h = clock_mod.to_hours(clk["date"], clk["hour"])
        deadline_h = clock_mod.to_hours(deadline["date"], deadline["hour"])
        if deadline_h <= now_h:
            raise EngineError("bad_deadline", "deadline must be in the future")

    if giver_type in ("npc", "pc"):
        if xp:
            raise EngineError("no_xp_reward", "NPC/PC quests cannot grant xp")
        if spawn:
            raise EngineError("spawn_world_only", "only world/GM quests may spawn rewards")
        escrow_from_type, escrow_from_id = giver_type, giver_id
    elif giver_type == "world":
        if spawn:
            if escrow_from_type:
                raise EngineError("bad_escrow", "spawn quests do not escrow from a holder")
            for item in items:
                if item not in g["items"]:
                    raise EngineError("unknown_item", f"no item {item} in this game")
        elif not escrow_from_type:
            raise EngineError("no_funding", "world quest needs --spawn or --escrow-from")
    else:
        raise EngineError("bad_ref", f"bad giver type {giver_type!r}")

    escrow = {"gold": 0, "items": []}
    if not spawn:
        holder, npcs_state = load_holder(root, escrow_from_type, escrow_from_id)
        who = f"{escrow_from_type}:{escrow_from_id}"
        _deduct_for_escrow(holder, gold, items, who)
        save_holder(root, escrow_from_type, escrow_from_id, holder, npcs_state)
        escrow = {"gold": gold, "items": list(items)}

    quest = {
        "id": quest_id, "title": title, "description": description,
        "giver": {"type": giver_type, "id": giver_id},
        "location": location,
        "status": "offered",
        "created": {"date": clk["date"], "hour": clk["hour"]},
        "deadline": deadline,
        "accepted_by": [],
        "reward": {"gold": gold, "items": items, "xp": xp, "spawn": spawn},
        "escrow": escrow,
        "escrow_from": None if spawn else {"type": escrow_from_type, "id": escrow_from_id},
    }
    save_quest(root, quest)
    timeline.append_event(root, type_="quest", actors=[giver_id] if giver_id else [],
                          summary=f"quest offered: {title} ({quest_id})")
    story_log.post(root, "quest", ref=quest_id, name=title, event="offered")
    return quest


def accept(root: Path, quest_id: str, pcs: list[str]) -> dict:
    quest = check_expiry(root, load_quest(root, quest_id))
    if quest["status"] == "expired":
        raise EngineError("expired", f"quest {quest_id} has expired")
    if quest["status"] != "offered":
        raise EngineError("bad_status", f"quest {quest_id} is {quest['status']}, not offered")
    party = worldfs.read_yaml(worldfs.state(root, "party"))
    for pid in pcs:
        if pid not in party["members"]:
            raise EngineError("not_found", f"no such PC {pid}")
        sheet = worldfs.read_yaml(worldfs.state(root, f"party/{pid}"))
        if derive.is_dead(sheet):
            raise EngineError("dead", f"{pid} is dead and cannot accept quests")
    quest["status"] = "accepted"
    quest["accepted_by"] = list(pcs)
    save_quest(root, quest)
    timeline.append_event(root, type_="quest", actors=list(pcs),
                          summary=f"quest accepted: {quest['title']} ({quest_id})")
    story_log.post(root, "quest", ref=quest_id, name=quest["title"], event="accepted")
    return quest


def complete(root: Path, quest_id: str, to: list[str] | None = None) -> dict:
    """Pay out rewards and mark the quest completed. Gold splits evenly across
    recipients with any remainder going to the first; all item rewards go to the
    first recipient; xp is granted to every recipient. Recipients default to
    accepted_by when --to is omitted."""
    quest = check_expiry(root, load_quest(root, quest_id))
    if quest["status"] == "expired":
        raise EngineError("expired", f"quest {quest_id} has expired")
    if quest["status"] not in _ACTIVE_STATUSES:
        raise EngineError("bad_status", f"quest {quest_id} is {quest['status']}")
    recipients = list(to) if to else list(quest["accepted_by"])
    if not recipients:
        raise EngineError("no_recipients", "no recipients: pass --to or accept the quest first")
    party = worldfs.read_yaml(worldfs.state(root, "party"))
    for pid in recipients:
        if pid not in party["members"]:
            raise EngineError("not_found", f"no such PC {pid}")
        sheet = worldfs.read_yaml(worldfs.state(root, f"party/{pid}"))
        if derive.is_dead(sheet):
            raise EngineError("dead", f"{pid} is dead and cannot complete quests")

    reward = quest["reward"]
    gold, items, xp = reward["gold"], reward["items"], reward["xp"]
    n = len(recipients)
    shares = [gold // n + (gold % n if i == 0 else 0) for i in range(n)] if gold else [0] * n
    for pid, share in zip(recipients, shares):
        _pay_to_pc(root, pid, share, [])
    if items:
        _pay_to_pc(root, recipients[0], 0, items)

    granted = level_mod.grant_xp_to(root, recipients, xp, f"quest reward: {quest['title']}") if xp else []

    quest["escrow"] = {"gold": 0, "items": []}
    quest["status"] = "completed"
    quest["accepted_by"] = recipients
    save_quest(root, quest)
    timeline.append_event(root, type_="quest", actors=recipients,
                          summary=f"quest completed: {quest['title']} ({quest_id})",
                          delta={"recipients": recipients, "gold": shares, "items": items,
                                 "xp": xp if granted else 0})
    story_log.post(root, "quest", ref=quest_id, name=quest["title"], event="completed")
    return quest


def cancel(root: Path, quest_id: str) -> dict:
    quest = load_quest(root, quest_id)
    if quest["status"] not in _ACTIVE_STATUSES:
        raise EngineError("bad_status", f"quest {quest_id} is {quest['status']}")
    _refund_escrow(root, quest)
    quest["status"] = "cancelled"
    save_quest(root, quest)
    timeline.append_event(root, type_="quest", actors=[],
                          summary=f"quest cancelled: {quest['title']} ({quest_id})")
    story_log.post(root, "quest", ref=quest_id, name=quest["title"], event="cancelled")
    return quest


def _summary(quest: dict) -> dict:
    return {"id": quest["id"], "title": quest["title"], "status": quest["status"],
            "giver": quest["giver"], "location": quest.get("location"),
            "deadline": quest["deadline"],
            "accepted_by": quest["accepted_by"], "reward": quest["reward"]}


def list_quests(root: Path, status: str | None = None) -> list[dict]:
    """List quests. Side effect: any offered/accepted quest whose deadline has
    passed is transitioned to expired (with escrow refunded) before listing."""
    quests = [check_expiry(root, load_quest(root, qid)) for qid in list_quest_ids(root)]
    if status:
        quests = [q for q in quests if q["status"] == status]
    return [_summary(q) for q in quests]


def is_visible(quest: dict, at_location: str | None) -> bool:
    """Player-lens visibility for a single quest at the party's current location.
    An `offered` quest pinned to a `location` (its board) is only visible when the
    party is standing there; an offered quest with no location is visible
    everywhere; any quest the party has already engaged (accepted and onward) is
    always visible."""
    if quest["status"] != "offered":
        return True
    loc = quest.get("location")
    return loc is None or loc == at_location


def visible_quests(root: Path, *, lens: str = "gm", at_location: str | None = None) -> list[dict]:
    """The quests a given lens should see from a given party location. The GM lens
    sees everything; the player lens hides an offered quest whose board sits at a
    location the party is not currently at (the reveal-on-arrival rule). Shares
    list_quests' deadline-expiry side effect. This is the API the viewer calls."""
    quests = [check_expiry(root, load_quest(root, qid)) for qid in list_quest_ids(root)]
    if lens != "gm":
        quests = [q for q in quests if is_visible(q, at_location)]
    return [_summary(q) for q in quests]
