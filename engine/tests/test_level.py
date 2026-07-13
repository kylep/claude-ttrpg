import json

from typer.testing import CliRunner

from ttrpg_engine import worldfs
from ttrpg_engine.cli import app
from conftest import make_pc
from test_spells import CLERIC

runner = CliRunner()


def test_grant_and_levelup_cleric(wroot):
    make_pc(**CLERIC)
    res = runner.invoke(app, ["level", "up", "--actor", "pc-mira"])
    assert json.loads(res.stdout)["error"]["code"] == "not_ready"
    runner.invoke(app, ["xp", "grant", "--amount", "300", "--reason", "quest"])
    res = runner.invoke(app, ["--seed", "6", "level", "up", "--actor", "pc-mira"])
    assert res.exit_code == 0, res.stdout
    sheet = worldfs.read_yaml(wroot / "state" / "party" / "pc-mira.yaml")
    assert sheet["level"] == 2
    assert sheet["max_hp"] >= 11                       # 8+2 at L1, +>=1
    assert "bless" in sheet["spells_known"]
    assert sheet["spell_slots"][1]["max"] == 3
    assert sheet["spell_slots"][1]["current"] == 3     # was full, +1 max


def test_level_cap(wroot):
    make_pc(**CLERIC)
    runner.invoke(app, ["xp", "grant", "--amount", "9999", "--reason", "test"])
    runner.invoke(app, ["--seed", "1", "level", "up", "--actor", "pc-mira"])
    runner.invoke(app, ["--seed", "1", "level", "up", "--actor", "pc-mira"])
    res = runner.invoke(app, ["--seed", "1", "level", "up", "--actor", "pc-mira"])
    assert json.loads(res.stdout)["error"]["code"] == "max_level"
