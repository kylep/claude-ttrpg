import json
from pathlib import Path

from typer.testing import CliRunner

from ttrpg_engine import worldfs
from ttrpg_engine.cli import app
from ttrpg_engine.errors import EngineError

FIXTURE_GAME = Path(__file__).parent / "fixtures" / "minigame"

runner = CliRunner()


def test_init_world_cleans_up_on_failure(tmp_path, monkeypatch):
    import pytest
    dest = tmp_path / "brokenworld"

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(worldfs.shutil, "copytree", boom)
    with pytest.raises(EngineError) as exc:
        worldfs.init_world(dest, FIXTURE_GAME, "Doomed")
    assert exc.value.code == "init_failed"
    assert not dest.exists()          # partial world removed so a retry is clean


def test_init_world_layout(tmp_path):
    root = tmp_path / "w"
    worldfs.init_world(root, FIXTURE_GAME, "Testia")
    manifest = worldfs.read_yaml(root / "world.yaml")
    assert manifest["world"] == "Testia"
    assert manifest["game"]["name"] == "minigame"
    clock = worldfs.read_yaml(root / "state" / "clock.yaml")
    assert (str(clock["date"]), clock["hour"]) == ("1203-04-17", 9)
    party = worldfs.read_yaml(root / "state" / "party.yaml")
    assert party == {"members": [], "location": "town", "gold": 0, "stash": []}
    assert (root / "canon" / "maps" / "region.yaml").exists()
    assert (root / "timeline").is_dir() and (root / "sessions").is_dir()
    assert "renders/" in (root / ".gitignore").read_text()


def test_find_root_walks_up(tmp_path, monkeypatch):
    root = tmp_path / "w"
    worldfs.init_world(root, FIXTURE_GAME, "Testia")
    deep = root / "canon" / "maps"
    monkeypatch.chdir(deep)
    assert worldfs.find_root() == root
    monkeypatch.chdir(tmp_path)
    try:
        worldfs.find_root()
        raise AssertionError("should have raised")
    except EngineError as e:
        assert e.code == "no_world"


def test_state_get(wroot):
    res = runner.invoke(app, ["state", "get", "clock", "--key", "hour"])
    assert res.exit_code == 0
    assert json.loads(res.stdout) == {"path": "clock", "key": "hour", "value": 9}


def test_cli_world_init_happy_path(tmp_path):
    dest = tmp_path / "w2"
    res = runner.invoke(app, ["world", "init", str(dest), "--game", str(FIXTURE_GAME), "--name", "Cliia"])
    assert res.exit_code == 0
    payload = json.loads(res.stdout)
    assert "world" in payload and "path" in payload
    assert (dest / "renders").is_dir()
    assert (dest / "world.yaml").exists()


def test_cli_world_init_dirty_dest_fails_cleanly(tmp_path):
    dest = tmp_path / "dirty"
    (dest / "canon").mkdir(parents=True)
    res = runner.invoke(app, ["world", "init", str(dest), "--game", str(FIXTURE_GAME), "--name", "Dirtia"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "init_failed"
    assert not (dest / "world.yaml").exists()


def test_world_override_flag(tmp_path, wroot, monkeypatch):
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["--world", str(wroot), "state", "get", "clock", "--key", "hour"])
    assert res.exit_code == 0
    assert json.loads(res.stdout)["value"] == 9


def test_load_game_for(wroot):
    assert worldfs.load_game_for(wroot)["meta"]["name"] == "minigame"
