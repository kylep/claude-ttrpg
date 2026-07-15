import datetime
import os
import shutil
import tempfile
from importlib import resources
from pathlib import Path

import yaml

from ttrpg_engine import game as game_mod
from ttrpg_engine.errors import EngineError

# junk that should never be copied into a world's .claude/
_KIT_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo",
                                     "*.lock", "scheduled_tasks.lock")


def _package_data_dir(name: str) -> Path | None:
    """A data dir bundled inside the installed package, if present (wheels)."""
    try:
        cand = resources.files("ttrpg_engine") / name
        return Path(str(cand)) if cand.is_dir() else None
    except (ModuleNotFoundError, FileNotFoundError, NotADirectoryError, TypeError):
        return None


def _repo_dir(name: str) -> Path | None:
    """A repo-root sibling dir, available under an editable/dev install where
    the source tree is present (worldfs.py is <repo>/engine/src/ttrpg_engine/)."""
    cand = Path(__file__).resolve().parents[3] / name
    return cand if cand.is_dir() else None


def agent_kit_dir() -> Path | None:
    """The `.claude/` payload to install into a new world: a packaged
    `agent_kit/` (wheel) or the repo-root `.claude/` (editable dev). None if
    neither is available (a bare wheel install with no bundled kit)."""
    return _package_data_dir("agent_kit") or _repo_dir(".claude")


def _bundled_game(name: str) -> Path | None:
    """Resolve a game by name against the engine's games registry (packaged
    `games/` or the repo `games/`), so a world stays loadable when its stored
    absolute path is not valid on this machine."""
    for base in (_package_data_dir("games"), _repo_dir("games")):
        if base is not None and (base / name).is_dir():
            return base / name
    return None


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
    gi = manifest["game"]
    path = Path(gi["path"])
    if path.is_dir():
        return game_mod.load(path)
    # the stored absolute path is not valid here (e.g. the world was cloned to
    # another machine) — fall back to the game registry by name.
    fallback = _bundled_game(gi.get("name", ""))
    if fallback is not None:
        return game_mod.load(fallback)
    raise EngineError("game_not_found",
                      f"game path {path} does not exist and no bundled game "
                      f"named {gi.get('name')!r} was found")


def init_world(dest: Path, game_path: Path, name: str) -> None:
    dest = Path(dest)
    if (dest / "world.yaml").exists():
        raise EngineError("exists", f"{dest} is already a world")
    errors = game_mod.validate(game_path)
    if errors:
        raise EngineError("game_invalid", "; ".join(errors))
    g = game_mod.load(game_path)
    preexisting = dest.exists()
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
        # install the GM agent + skills so the world is playable without a
        # manual copy; skipped only on a bare wheel install with no bundled kit
        kit = agent_kit_dir()
        if kit is not None:
            shutil.copytree(kit, dest / ".claude", ignore=_KIT_IGNORE,
                            dirs_exist_ok=True)
        # world.yaml is the commit point: write it last so a crash mid-init
        # never leaves a manifest behind (which would make retries think the
        # world already exists).
        write_yaml(dest / "world.yaml", {
            "world": name,
            "game": {"name": g["meta"]["name"], "version": str(g["meta"]["version"]),
                     "path": str(Path(game_path).resolve())},
            "created": datetime.date.today().isoformat(),
        })
    except Exception as e:
        # world.yaml is written last, so reaching here means a partial init.
        # Remove what we created (only if the dir is ours) so a retry is clean.
        if not preexisting and dest.exists() and not (dest / "world.yaml").exists():
            shutil.rmtree(dest, ignore_errors=True)
        if isinstance(e, OSError):
            raise EngineError("init_failed", f"cannot initialize {dest}: {e}")
        raise
