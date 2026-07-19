import re
from pathlib import Path

from ttrpg_engine import derive, story_log, timeline, worldfs
from ttrpg_engine.derive import attr_mod
from ttrpg_engine.errors import EngineError
from ttrpg_engine.game import ATTRS


def slugify(name: str) -> str:
    """Lowercase, hyphenate, and trim a display name into an id fragment."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


# Point-buy: each attribute is bought 8..15 before racial bonuses, spending from
# a 27-point budget. Balance-neutral to the standard array, which costs exactly 27.
_POINT_BUY_COST = {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9}
_POINT_BUY_BUDGET = 27


def _pointbuy_scores(spec: dict[str, int]) -> dict[str, int]:
    """Validate a point-buy spread: every attribute set to a 8..15 score whose
    total cost is within the budget. Raises bad_pointbuy on any violation."""
    if sorted(spec) != sorted(ATTRS):
        raise EngineError("bad_pointbuy", f"point-buy must cover exactly {ATTRS}")
    total = 0
    for attr, score in spec.items():
        if score not in _POINT_BUY_COST:
            raise EngineError("bad_pointbuy",
                              f"{attr}={score} out of range (each score must be 8..15)")
        total += _POINT_BUY_COST[score]
    if total > _POINT_BUY_BUDGET:
        raise EngineError("bad_pointbuy",
                          f"point-buy costs {total} points, over the {_POINT_BUY_BUDGET}-point budget")
    return dict(spec)


def _flavor(text) -> str:
    """Normalize a ruleset description (often a folded YAML scalar) to a clean
    one-liner; missing descriptions become an empty string."""
    return " ".join((text or "").split())


def _load_race_lore(g: dict) -> dict:
    """Load the content-side race lore (content/lore/races.yaml), failing open
    to {} if it's absent, unreadable, or not a mapping. This file is optional
    world content — the engine works fine without it."""
    content = g.get("content_dir")
    if content is None:
        return {}
    lore_path = Path(content) / "lore" / "races.yaml"
    if not lore_path.exists():
        return {}
    try:
        data = worldfs.read_yaml(lore_path)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _race_image(g: dict, race_lore: dict, name: str):
    """Resolve a race's portrait path from its lore metadata, failing open:
    returns the declared (content-relative) image path ONLY when it is a
    non-empty string AND the file actually exists under the content dir;
    otherwise None. A missing field, missing lore file, or missing image file
    all degrade to None rather than raising — no race is required to have art."""
    content = g.get("content_dir")
    entry = race_lore.get(name) if isinstance(race_lore, dict) else None
    img = entry.get("image") if isinstance(entry, dict) else None
    if not (content is not None and isinstance(img, str) and img):
        return None
    try:
        return img if (Path(content) / img).exists() else None
    except OSError:
        return None


def options(g: dict) -> dict:
    """Everything a party-creation wizard needs to present the game's choices,
    resolved from the ruleset: the standard array, each race
    (bonuses/speed/flavor), and each class (hit die, caster attr, skill list and
    how many to pick, starting gear/gold, level-1 spells/features, plus a
    recommended attribute spread and skill pick as accept-in-one-tap defaults).
    `recommended_array` comes from the class's optional `attr_priority` (a full
    permutation of the six attributes, most to least important) and is null when
    the class doesn't declare one. Read-only — mutates nothing."""
    items, spells = g.get("items", {}), g.get("spells", {})
    array = g["core"]["standard_array"]

    def _item(iid):
        it = items.get(iid, {})
        return {"id": iid, "name": iid.replace("_", " "),
                "type": it.get("type"), "description": _flavor(it.get("description"))}

    def _spell(sid):
        sp = spells.get(sid, {})
        return {"id": sid, "name": sid.replace("_", " "),
                "level": sp.get("level"), "description": _flavor(sp.get("description"))}

    def _recommended_array(cls):
        pri = cls.get("attr_priority")
        if not pri or sorted(pri) != sorted(ATTRS):
            return None
        ranked = sorted(array, reverse=True)          # highest score to highest priority
        return {attr: ranked[i] for i, attr in enumerate(pri)}

    race_lore = _load_race_lore(g)
    races = {name: {"bonuses": r.get("bonuses", {}), "speed": r.get("speed"),
                    "description": _flavor(r.get("description")),
                    "image": _race_image(g, race_lore, name)}
             for name, r in g["races"].items()}
    classes = {}
    for name, c in g["classes"].items():
        level1 = c["levels"][1]
        classes[name] = {
            "name": name,
            "description": _flavor(c.get("description")),
            "hit_die": c["hit_die"],
            "cast_attr": c.get("cast_attr"),
            "skills": list(c["skills"]),
            "skill_choices": c["skill_choices"],
            "recommended_skills": list(c["skills"][:c["skill_choices"]]),
            "starting_gear": [_item(i) for i in c["starting_gear"]],
            "starting_gold": c["starting_gold"],
            "level1_spells": [_spell(s) for s in level1["spells"]],
            "level1_features": list(level1["features"]),
            "recommended_array": _recommended_array(c),
        }
    return {"attributes": list(ATTRS), "standard_array": list(array),
            "races": races, "classes": classes}


def set_control(root: Path, pc_id: str, played_by: str) -> dict:
    """Set (or reassign) who runs an existing PC at the table — a player's
    name, or "GM". Retrofits sheets created before the field existed."""
    path = worldfs.state(root, f"party/{pc_id}")
    if not path.exists():
        raise EngineError("not_found", f"no PC {pc_id}")
    sheet = worldfs.read_yaml(path)
    sheet["played_by"] = played_by
    worldfs.write_yaml(path, sheet)
    return {"pc": pc_id, "played_by": played_by}


def create(root: Path, g: dict, *, name: str, cls_name: str, race_name: str,
           assign: dict[str, int] | None = None, skills: list[str],
           played_by: str | None = None,
           point_buy: dict[str, int] | None = None) -> dict:
    """Validate the choices, then build, persist, and return a level-1 PC sheet;
    also appends the PC to the party file, logs a timeline event, and drops the
    character's card into the story log. Starting scores come from exactly one of
    `assign` (the ruleset's standard array, every attribute covered) or
    `point_buy` (8..15 per attribute within the 27-point budget). `played_by`
    records who runs the character at the table (a player's name, or "GM")."""
    if cls_name not in g["classes"]:
        raise EngineError("unknown_class", f"no class {cls_name}")
    if race_name not in g["races"]:
        raise EngineError("unknown_race", f"no race {race_name}")
    cls, race = g["classes"][cls_name], g["races"][race_name]
    if (assign is None) == (point_buy is None):
        raise EngineError("bad_assign", "pass exactly one of assign or point_buy")
    if point_buy is not None:
        base = _pointbuy_scores(point_buy)
    else:
        if sorted(assign) != sorted(ATTRS):
            raise EngineError("bad_assign", f"assign must cover exactly {ATTRS}")
        if sorted(assign.values()) != sorted(g["core"]["standard_array"]):
            raise EngineError("bad_assign", f"values must be the standard array {g['core']['standard_array']}")
        base = assign
    if (len(skills) != cls["skill_choices"] or len(set(skills)) != len(skills)
            or not set(skills) <= set(cls["skills"])):
        raise EngineError("bad_skills", f"pick exactly {cls['skill_choices']} of {cls['skills']}")
    attrs = {a: base[a] + race.get("bonuses", {}).get(a, 0) for a in ATTRS}
    prof = g["progression"]["proficiency"][1]
    level1 = cls["levels"][1]
    slug = slugify(name)
    if not slug:
        raise EngineError("bad_name", f"name {name!r} has no usable letters or digits")
    pc_id = f"pc-{slug}"
    if worldfs.state(root, f"party/{pc_id}").exists():
        raise EngineError("exists", f"{pc_id} already exists")
    party = worldfs.read_yaml(worldfs.state(root, "party"))
    max_hp = max(1, cls["hit_die"] + attr_mod(attrs["CON"]))
    sheet = {
        "id": pc_id, "name": name, "class": cls_name, "race": race_name,
        "level": 1, "xp": 0, "attributes": attrs,
        "max_hp": max_hp, "hp": max_hp,
        "ac": 0,
        "speed": race["speed"], "proficiency": prof, "skills": skills,
        "attacks": [],
        "spells_known": list(level1["spells"]),
        "spell_slots": {lvl: {"max": n, "current": n} for lvl, n in level1["slots"].items()},
        "features": list(level1["features"]),
        "inventory": [{"item": i, "qty": 1, "equipped": True} for i in cls["starting_gear"]],
        "gold": cls["starting_gold"], "effects": [],
        "location": party["location"],
    }
    if played_by:
        sheet["played_by"] = played_by
    derive.recompute(sheet, g)
    worldfs.write_yaml(worldfs.state(root, f"party/{pc_id}"), sheet)
    party["members"].append(pc_id)
    worldfs.write_yaml(worldfs.state(root, "party"), party)
    timeline.append_event(root, type_="character", actors=[pc_id],
                          summary=f"{name} the {race_name} {cls_name} joins the party")
    story_log.post(root, "character", ref=pc_id, name=name)
    return sheet
