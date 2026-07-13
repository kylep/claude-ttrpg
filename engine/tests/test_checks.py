import json

from typer.testing import CliRunner

from ttrpg_engine.cli import app
from conftest import make_pc

runner = CliRunner()


def test_check_applies_proficiency(wroot):
    pc = make_pc()  # dwarf fighter, WIS 12 (+1), proficient in perception (prof +2)
    res = runner.invoke(app, ["--seed", "3", "check", "--actor", pc,
                              "--attr", "WIS", "--skill", "perception", "--dc", "12"])
    assert res.exit_code == 0, res.stdout
    data = json.loads(res.stdout)
    assert data["modifier"] == 3
    assert data["total"] == data["natural"] + 3
    assert data["success"] == (data["total"] >= 12)


def test_check_unknown_actor_fails(wroot):
    res = runner.invoke(app, ["check", "--actor", "pc-nobody", "--attr", "STR", "--dc", "10"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "not_found"


def test_check_unknown_attr_fails(wroot):
    pc = make_pc()
    res = runner.invoke(app, ["check", "--actor", pc, "--attr", "WSI", "--dc", "10"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "unknown_attr"
