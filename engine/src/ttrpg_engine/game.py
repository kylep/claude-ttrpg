from pathlib import Path

import yaml

from ttrpg_engine.errors import EngineError

_RULESET_FILES = ["core", "attributes", "races", "spells", "effects",
                  "combat", "recovery", "progression", "economy", "items",
                  "features"]
ATTRS = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]


def _read(path: Path):
    if not path.exists():
        raise EngineError("game_invalid", f"missing file: {path}")
    return yaml.safe_load(path.read_text()) or {}


def load(path: Path) -> dict:
    path = Path(path)
    g = {"meta": _read(path / "game.yaml"), "content_dir": path / "content"}
    for name in _RULESET_FILES:
        g[name] = _read(path / "ruleset" / f"{name}.yaml")
    g["classes"] = {}
    classes_dir = path / "ruleset" / "classes"
    if not classes_dir.is_dir():
        raise EngineError("game_invalid", f"missing dir: {classes_dir}")
    for f in sorted(classes_dir.glob("*.yaml")):
        g["classes"][f.stem] = _read(f)
    return g


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        g = load(path)
    except EngineError as e:
        return [e.message]
    max_level = g["progression"].get("max_level", 1)
    for cname, cls in g["classes"].items():
        for lvl in range(1, max_level + 1):
            if lvl not in cls.get("levels", {}):
                errors.append(f"class {cname}: missing level {lvl} row")
        for item in cls.get("starting_gear", []):
            if item not in g["items"]:
                errors.append(f"class {cname}: unknown starting item {item}")
        for row in cls.get("levels", {}).values():
            for spell in row.get("spells", []):
                if spell not in g["spells"]:
                    errors.append(f"class {cname}: unknown spell {spell}")
            for tag in row.get("features", []):
                if tag not in g["features"]:
                    errors.append(f"class {cname}: unknown feature {tag}")
    for mname, mon in _bestiary(g).items():
        for field in ["name", "ac", "hp", "speed", "attributes", "attacks", "xp"]:
            if field not in mon:
                errors.append(f"monster {mname}: missing {field}")
    region = g["content_dir"] / "maps" / "region.yaml"
    if region.exists():
        rmap = yaml.safe_load(region.read_text()) or {}
        nodes = set(rmap.get("nodes", {}))
        for edge in rmap.get("edges", []):
            for end in edge.get("between", []):
                if end not in nodes:
                    errors.append(f"region edge references unknown node {end}")
    else:
        errors.append("missing content/maps/region.yaml")
    return errors


def _bestiary(g: dict) -> dict:
    out = {}
    bdir = g["content_dir"] / "bestiary"
    if bdir.is_dir():
        for f in sorted(bdir.glob("*.yaml")):
            out[f.stem] = yaml.safe_load(f.read_text()) or {}
    return out


def bestiary_entry(g: dict, monster_type: str) -> dict:
    entry = _bestiary(g).get(monster_type)
    if entry is None:
        raise EngineError("unknown_monster", f"no bestiary entry: {monster_type}")
    return entry
