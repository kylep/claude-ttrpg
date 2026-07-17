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


def test_create_rejects_duplicate_skills(wroot):
    res = runner.invoke(app, ["char", "create", "--name", "Dup", "--class", "fighter",
                              "--race", "human", "--assign", ASSIGN,
                              "--skills", "athletics,athletics"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "bad_skills"


def test_create_rejects_padded_duplicate_skills(wroot):
    res = runner.invoke(app, ["char", "create", "--name", "Pad", "--class", "fighter",
                              "--race", "human", "--assign", ASSIGN,
                              "--skills", "athletics,athletics,perception"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "bad_skills"


def _create(**over):
    args = {"name": "Borin", "class": "fighter", "race": "dwarf",
            "assign": ASSIGN, "skills": "athletics,perception"}
    args.update(over)
    flat = []
    for k, v in args.items():
        flat += [f"--{k}", v]
    return runner.invoke(app, ["char", "create", *flat])


def test_create_rejects_unknown_class(wroot):
    assert json.loads(_create(**{"class": "paladin"}).stdout)["error"]["code"] == "unknown_class"


def test_create_rejects_unknown_race(wroot):
    assert json.loads(_create(race="orc").stdout)["error"]["code"] == "unknown_race"


def test_create_rejects_duplicate_pc(wroot):
    assert _create().exit_code == 0
    assert json.loads(_create().stdout)["error"]["code"] == "exists"


def test_create_rejects_empty_slug_name(wroot):
    # "!!!" has no alphanumerics -> pc- id would be degenerate
    assert json.loads(_create(name="!!!").stdout)["error"]["code"] == "bad_name"


def test_char_control_sets_and_reassigns_played_by(wroot):
    assert _create().exit_code == 0                      # pc-borin, no --played-by
    p = wroot / "state" / "party" / "pc-borin.yaml"
    assert "played_by" not in worldfs.read_yaml(p)
    res = runner.invoke(app, ["char", "control", "--pc", "pc-borin", "--played-by", "GM"])
    assert res.exit_code == 0, res.stdout
    assert worldfs.read_yaml(p)["played_by"] == "GM"
    runner.invoke(app, ["char", "control", "--pc", "pc-borin", "--played-by", "Kyle"])
    assert worldfs.read_yaml(p)["played_by"] == "Kyle"    # reassigns
    res = runner.invoke(app, ["char", "control", "--pc", "pc-nobody", "--played-by", "GM"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "not_found"


def test_char_options_cli_shape(wroot):
    res = runner.invoke(app, ["char", "options"])
    assert res.exit_code == 0, res.stdout
    opts = json.loads(res.stdout)
    assert opts["standard_array"] == [15, 14, 13, 12, 10, 8]
    assert set(opts["attributes"]) == {"STR", "DEX", "CON", "INT", "WIS", "CHA"}
    f = opts["classes"]["fighter"]
    assert f["skill_choices"] == 2 and len(f["recommended_skills"]) == 2
    assert set(f["recommended_skills"]) <= set(f["skills"])
    assert f["starting_gear"][0]["id"] == "chain_mail"
    assert opts["races"]["dwarf"]["bonuses"] == {"CON": 2}
    # minigame classes declare no attr_priority -> no recommended spread
    assert f["recommended_array"] is None


def test_char_options_recommended_array_maps_priority():
    from pathlib import Path

    from ttrpg_engine import game
    ref = Path(__file__).resolve().parents[2] / "games" / "reference"
    g = game.load(ref)
    opts = chargen.options(g)
    rec = opts["classes"]["fighter"]["recommended_array"]
    # a recommendation the engine would accept: every attribute, standard array
    assert sorted(rec) == sorted(opts["attributes"])
    assert sorted(rec.values()) == sorted(opts["standard_array"])
    top = g["classes"]["fighter"]["attr_priority"][0]
    assert rec[top] == max(opts["standard_array"])             # best score to top priority
