import datetime
import os
import shutil
import tempfile
from pathlib import Path

import yaml

from ttrpg_engine import game as game_mod
from ttrpg_engine.errors import EngineError


def find_root(start: Path | None = None) -> Path:
    cur = (start or Path.cwd()).resolve()
    for p in [cur, *cur.parents]:
        if (p / "world.yaml").exists():
            return p
    raise EngineError("no_world", "no world.yaml found from cwd upward (use --world or cd into a world repo)")


def read_yaml(path: Path) -> dict:
    if not path.exists():
        raise EngineError("not_found", f"missing state file: {path}")
    return yaml.safe_load(path.read_text()) or {}


def write_yaml(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
    os.replace(tmp, path)


def state(root: Path, rel: str) -> Path:
    return root / "state" / f"{rel}.yaml"


def pc_location(sheet: dict, party: dict) -> str:
    """A PC's current location: the sheet's own `location` if set, else the
    party anchor. Old-world sheets (pre-party-split) lack the key entirely."""
    return sheet.get("location", party["location"])


def load_game_for(root: Path) -> dict:
    manifest = read_yaml(root / "world.yaml")
    return game_mod.load(Path(manifest["game"]["path"]))


def init_world(dest: Path, game_path: Path, name: str) -> None:
    dest = Path(dest)
    if (dest / "world.yaml").exists():
        raise EngineError("exists", f"{dest} is already a world")
    errors = game_mod.validate(game_path)
    if errors:
        raise EngineError("game_invalid", "; ".join(errors))
    g = game_mod.load(game_path)
    try:
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copytree(g["content_dir"], dest / "canon")
        write_yaml(state(dest, "clock"), {"date": str(g["meta"]["start_date"]),
                                          "hour": g["meta"]["start_hour"]})
        write_yaml(state(dest, "party"), {"members": [], "location": g["meta"]["start_location"],
                                          "gold": 0, "stash": []})
        write_yaml(state(dest, "session"), {"current": 0})
        (dest / "timeline").mkdir()
        (dest / "sessions").mkdir()
        (dest / "renders").mkdir()
        (dest / ".gitignore").write_text("renders/\n")
        # world.yaml is the commit point: write it last so a crash mid-init
        # never leaves a manifest behind (which would make retries think the
        # world already exists).
        write_yaml(dest / "world.yaml", {
            "world": name,
            "game": {"name": g["meta"]["name"], "version": str(g["meta"]["version"]),
                     "path": str(Path(game_path).resolve())},
            "created": datetime.date.today().isoformat(),
        })
    except OSError as e:
        raise EngineError("init_failed", f"cannot initialize {dest}: {e}")
