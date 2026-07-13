import json

from typer.testing import CliRunner

from ttrpg_engine import combat, worldfs
from ttrpg_engine.cli import app
from conftest import make_pc
from test_spells import CLERIC

runner = CliRunner()


def test_short_rest_heals_and_advances_clock(wroot):
    make_pc()
    combat.apply_damage(wroot, "pc-borin", 6, source="test")
    res = runner.invoke(app, ["--seed", "8", "rest", "--type", "short"])
    assert res.exit_code == 0, res.stdout
    sheet = worldfs.read_yaml(wroot / "state" / "party" / "pc-borin.yaml")
    assert 13 - 6 < sheet["hp"] <= 13
    clock = worldfs.read_yaml(wroot / "state" / "clock.yaml")
    assert clock["hour"] == 10


def test_long_rest_restores_everything(wroot):
    make_pc(**CLERIC)
    runner.invoke(app, ["cast", "--caster", "pc-mira", "--spell", "cure_wounds"])
    combat.apply_damage(wroot, "pc-mira", 4, source="test")
    combat.set_effect(wroot, "pc-mira", "poisoned", -1)
    res = runner.invoke(app, ["rest", "--type", "long"])
    assert res.exit_code == 0, res.stdout
    sheet = worldfs.read_yaml(wroot / "state" / "party" / "pc-mira.yaml")
    assert sheet["hp"] == sheet["max_hp"]
    assert sheet["spell_slots"][1]["current"] == 2
    assert sheet["effects"] == []
    clock = worldfs.read_yaml(wroot / "state" / "clock.yaml")
    assert clock["hour"] == 17


def test_rest_blocked_in_encounter(wroot):
    make_pc()
    runner.invoke(app, ["--seed", "5", "encounter", "start", "maps/encounters/skirmish.yaml"])
    res = runner.invoke(app, ["rest", "--type", "short"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "encounter_active"


def test_short_rest_clears_death_state(wroot):
    make_pc()
    combat.apply_damage(wroot, "pc-borin", 13, source="test")
    res = runner.invoke(app, ["--seed", "8", "rest", "--type", "short"])
    assert res.exit_code == 0, res.stdout
    sheet = worldfs.read_yaml(wroot / "state" / "party" / "pc-borin.yaml")
    assert sheet["hp"] > 0
    names = {e["name"] for e in sheet["effects"]}
    assert "dying" not in names and "unconscious" not in names
    assert "death_saves" not in sheet
