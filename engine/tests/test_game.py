import json
import shutil
from pathlib import Path

from typer.testing import CliRunner

from ttrpg_engine import game
from ttrpg_engine.cli import app

FIXTURE_GAME = Path(__file__).parent / "fixtures" / "minigame"

runner = CliRunner()


def test_load_keys():
    g = game.load(FIXTURE_GAME)
    assert g["meta"]["name"] == "minigame"
    assert g["classes"]["fighter"]["hit_die"] == 10
    assert g["items"]["dagger"]["finesse"] is True
    assert g["content_dir"] == FIXTURE_GAME / "content"


def test_validate_ok():
    assert game.validate(FIXTURE_GAME) == []


def test_validate_catches_bad_edge_and_missing_class_file(tmp_path):
    broken = tmp_path / "broken"
    shutil.copytree(FIXTURE_GAME, broken)
    (broken / "ruleset" / "classes" / "fighter.yaml").unlink()
    region = broken / "content" / "maps" / "region.yaml"
    region.write_text(region.read_text().replace("cave]", "nowhere]"))
    errors = game.validate(broken)
    assert any("nowhere" in e for e in errors)


def test_validate_catches_unknown_feature_tag(tmp_path):
    broken = tmp_path / "broken"
    shutil.copytree(FIXTURE_GAME, broken)
    fpath = broken / "ruleset" / "classes" / "fighter.yaml"
    fpath.write_text(fpath.read_text().replace("second_wind", "nonexistent_feature"))
    errors = game.validate(broken)
    assert any("class fighter: unknown feature nonexistent_feature" in e for e in errors)


def test_cli_validate():
    res = runner.invoke(app, ["game", "validate", str(FIXTURE_GAME)])
    assert res.exit_code == 0
    assert json.loads(res.stdout) == {"valid": True, "game": "minigame", "errors": []}
