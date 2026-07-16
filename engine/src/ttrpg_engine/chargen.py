import re
from pathlib import Path

from ttrpg_engine import derive, story_log, timeline, worldfs
from ttrpg_engine.derive import attr_mod
from ttrpg_engine.errors import EngineError
from ttrpg_engine.game import ATTRS


def slugify(name: str) -> str:
    """Lowercase, hyphenate, and trim a display name into an id fragment."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _flavor(text) -> str:
    """Normalize a ruleset description (often a folded YAML scalar) to a clean
    one-liner; missing descriptions become an empty string."""
    return " ".join((text or "").split())


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

    races = {name: {"bonuses": r.get("bonuses", {}), "speed": r.get("speed"),
                    "description": _flavor(r.get("description"))}
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


def create(root: Path, g: dict, *, name: str, cls_name: str, race_name: str,
           assign: dict[str, int], skills: list[str],
           played_by: str | None = None) -> dict:
    """Validate the choices, then build, persist, and return a level-1 PC sheet;
    also appends the PC to the party file, logs a timeline event, and drops the
    character's card into the story log. `assign` must cover every attribute
    using exactly the ruleset's standard array. `played_by` records who runs
    the character at the table (a player's name, or "GM")."""
    if cls_name not in g["classes"]:
        raise EngineError("unknown_class", f"no class {cls_name}")
    if race_name not in g["races"]:
        raise EngineError("unknown_race", f"no race {race_name}")
    cls, race = g["classes"][cls_name], g["races"][race_name]
    if sorted(assign) != sorted(ATTRS):
        raise EngineError("bad_assign", f"assign must cover exactly {ATTRS}")
    if sorted(assign.values()) != sorted(g["core"]["standard_array"]):
        raise EngineError("bad_assign", f"values must be the standard array {g['core']['standard_array']}")
    if (len(skills) != cls["skill_choices"] or len(set(skills)) != len(skills)
            or not set(skills) <= set(cls["skills"])):
        raise EngineError("bad_skills", f"pick exactly {cls['skill_choices']} of {cls['skills']}")
    attrs = {a: assign[a] + race.get("bonuses", {}).get(a, 0) for a in ATTRS}
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
