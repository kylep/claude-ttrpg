import datetime
import hashlib
import os
import shutil
import tempfile
from importlib import metadata, resources
from pathlib import Path

import yaml

from ttrpg_engine import game as game_mod
from ttrpg_engine.errors import EngineError

# junk that should never be copied into a world's .claude/
_KIT_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo",
                                     "*.lock", "scheduled_tasks.lock")
# the kit subtrees an upgrade manages (behavioral content); settings.json is
# left to the operator unless --force, and is not part of the version hash
_KIT_MANAGED = ("agents", "skills", "hooks")
_JUNK_SUFFIXES = (".pyc", ".pyo", ".lock")


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


# --- agent-kit versioning + upgrade ---------------------------------------

def engine_version() -> str:
    try:
        return metadata.version("ttrpg-engine")
    except metadata.PackageNotFoundError:
        return "0"


def _is_kit_junk(p: Path) -> bool:
    return ("__pycache__" in p.parts or p.suffix in _JUNK_SUFFIXES
            or p.name == "scheduled_tasks.lock")


def _kit_managed_files(base: Path) -> list[tuple[str, Path]]:
    """(relpath, abspath) for the kit files an upgrade manages — everything
    under agents/skills/hooks, minus junk — sorted for a stable hash."""
    out = []
    for sub in _KIT_MANAGED:
        d = base / sub
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*")):
            if p.is_file() and not _is_kit_junk(p):
                out.append((str(p.relative_to(base)), p))
    return sorted(out)


def kit_hash(kit_dir: Path) -> str:
    """Content hash of a kit's managed files (path + bytes), so any skill,
    agent, or hook change moves the hash."""
    h = hashlib.sha256()
    for rel, abspath in _kit_managed_files(kit_dir):
        h.update(rel.encode())
        h.update(b"\0")
        h.update(abspath.read_bytes())
        h.update(b"\0")
    return "sha256:" + h.hexdigest()


def _kit_version_path(root: Path) -> Path:
    return root / ".claude" / ".kit-version"


def write_kit_version(root: Path, kit_dir: Path) -> dict:
    marker = {"engine_version": engine_version(),
              "kit_hash": kit_hash(kit_dir),
              "installed": datetime.date.today().isoformat()}
    write_yaml(_kit_version_path(root), marker)
    return marker


def read_kit_version(root: Path) -> dict | None:
    p = _kit_version_path(root)
    return read_yaml(p) if p.exists() else None


def check_kit(root: Path) -> dict:
    """Compare the world's installed kit to the engine's current kit."""
    kit = agent_kit_dir()
    if kit is None:
        return {"status": "no_kit", "engine_version": engine_version()}
    current = kit_hash(kit)
    stored = read_kit_version(root)
    if stored is None:
        return {"status": "unknown", "engine_version": engine_version(),
                "current_hash": current}
    return {
        "status": "up_to_date" if stored.get("kit_hash") == current else "outdated",
        "world_engine_version": stored.get("engine_version"),
        "engine_version": engine_version(),
        "world_hash": stored.get("kit_hash"),
        "current_hash": current,
    }


def upgrade_agent_kit(root: Path, *, dry_run: bool = False, force: bool = False) -> dict:
    """Re-sync the world's .claude/ agents/skills/hooks with the engine's
    current kit: copy changed files, remove kit files that no longer exist,
    and (only with force) overwrite settings.json. The world is a git repo,
    so the operator reviews the diff and commits — the upgrade is a save
    point, fully reversible."""
    kit = agent_kit_dir()
    if kit is None:
        raise EngineError("no_kit", "no agent kit available to upgrade from")
    dest = root / ".claude"
    if not dest.is_dir():
        raise EngineError("no_kit_installed",
                          "this world has no .claude/ to upgrade (create it with a newer engine)")
    managed = _kit_managed_files(kit)
    kit_rels = {rel for rel, _ in managed}
    changed = [rel for rel, src in managed
               if not (dest / rel).exists() or (dest / rel).read_bytes() != src.read_bytes()]
    removed = [rel for rel, _ in _kit_managed_files(dest) if rel not in kit_rels]

    settings_src = kit / "settings.json"
    if force and settings_src.is_file():
        cur = dest / "settings.json"
        if not cur.exists() or cur.read_bytes() != settings_src.read_bytes():
            changed.append("settings.json")

    if not dry_run:
        for rel, src in managed:
            dst = dest / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        for rel in removed:
            (dest / rel).unlink(missing_ok=True)
        if force and settings_src.is_file():
            shutil.copy2(settings_src, dest / "settings.json")
        write_kit_version(root, kit)
    return {"changed": sorted(changed), "removed": sorted(removed),
            "dry_run": dry_run, "engine_version": engine_version()}


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
    """Atomic YAML write (temp file + os.replace) so a crash mid-write never
    leaves a truncated state file."""
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
            write_kit_version(dest, kit)
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
