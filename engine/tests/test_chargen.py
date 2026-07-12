import json

from typer.testing import CliRunner

from ttrpg_engine import chargen, worldfs
from ttrpg_engine.cli import app
from ttrpg_engine.errors import EngineError

runner = CliRunner()

ASSIGN = "STR=15,CON=14,DEX=13,WIS=12,INT=10,CHA=8"


def test_attr_mod():
    assert chargen.attr_mod(15) == 2
    assert chargen.attr_mod(10) == 0
    assert chargen.attr_mod(8) == -1


def test_cli_create_fighter(wroot):
    res = runner.invoke(app, ["char", "create", "--name", "Borin", "--class", "fighter",
                              "--race", "dwarf", "--assign", ASSIGN,
                              "--skills", "athletics,perception"])
    assert res.exit_code == 0, res.stdout
    sheet = worldfs.read_yaml(wroot / "state" / "party" / "pc-borin.yaml")
    assert sheet["attributes"]["CON"] == 16          # 14 + dwarf +2
    assert sheet["max_hp"] == 13                     # d10 max + CON mod 3
    assert sheet["ac"] == 16                         # chain mail, no dex
    atk = sheet["attacks"][0]
    assert atk == {"name": "longsword", "attack_mod": 4, "damage": "1d8+2", "range": 1}
    party = worldfs.read_yaml(wroot / "state" / "party.yaml")
    assert party["members"] == ["pc-borin"]
    assert len(list((wroot / "timeline").glob("*.yaml"))) == 1


def test_create_rejects_bad_array(wroot):
    from conftest import FIXTURE_GAME
    from ttrpg_engine import game
    g = game.load(FIXTURE_GAME)
    try:
        chargen.create(wroot, g, name="X", cls_name="fighter", race_name="human",
                       assign={"STR": 18, "DEX": 14, "CON": 13, "INT": 12, "WIS": 10, "CHA": 8},
                       skills=["athletics", "perception"])
        raise AssertionError("should have raised")
    except EngineError as e:
        assert e.code == "bad_assign"


def test_cleric_gets_spells_and_slots(wroot):
    res = runner.invoke(app, ["char", "create", "--name", "Mira", "--class", "cleric",
                              "--race", "human", "--assign",
                              "WIS=15,CON=14,STR=13,DEX=12,INT=10,CHA=8",
                              "--skills", "insight,medicine"])
    assert res.exit_code == 0, res.stdout
    # read from disk, not the CLI JSON: JSON stringifies the int slot-level keys
    sheet = worldfs.read_yaml(wroot / "state" / "party" / "pc-mira.yaml")
    assert sheet["spells_known"] == ["sacred_flame", "cure_wounds"]
    assert sheet["spell_slots"] == {1: {"max": 2, "current": 2}}
