import json

from typer.testing import CliRunner

from ttrpg_engine import combat, worldfs
from ttrpg_engine.cli import app
from conftest import make_pc

runner = CliRunner()


def _sheet(wroot):
    return worldfs.read_yaml(worldfs.state(wroot, "party/pc-borin"))


def test_wound_add_and_heal_all(wroot):
    make_pc()
    res = runner.invoke(app, ["wound", "add", "--actor", "pc-borin",
                              "--text", "arrow in the leg"])
    assert res.exit_code == 0, res.stdout
    out = json.loads(res.stdout)
    assert out["wounds"] == [{"text": "arrow in the leg", "severity": "serious"}]
    assert _sheet(wroot)["wounds"][0]["text"] == "arrow in the leg"   # persisted
    res = runner.invoke(app, ["wound", "heal", "--actor", "pc-borin", "--all"])
    assert res.exit_code == 0, res.stdout
    assert json.loads(res.stdout)["wounds"] == []
    assert _sheet(wroot)["wounds"] == []


def test_wound_heal_by_index(wroot):
    make_pc()
    for t in ("cut lip", "broken rib"):
        runner.invoke(app, ["wound", "add", "--actor", "pc-borin",
                            "--text", t, "--severity", "minor"])
    res = runner.invoke(app, ["wound", "heal", "--actor", "pc-borin", "--index", "0"])
    assert res.exit_code == 0, res.stdout
    out = json.loads(res.stdout)
    assert [w["text"] for w in out["wounds"]] == ["broken rib"]
    assert out["healed"][0]["text"] == "cut lip"


def test_wound_rejects_bad_severity_and_index(wroot):
    make_pc()
    res = runner.invoke(app, ["wound", "add", "--actor", "pc-borin",
                              "--text", "x", "--severity", "fatal"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "bad_severity"
    res = runner.invoke(app, ["wound", "heal", "--actor", "pc-borin", "--index", "5"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "bad_index"


def test_full_heal_clears_wounds(wroot):
    make_pc()
    combat.add_wound(wroot, "pc-borin", "arrow in the leg")
    sheet = _sheet(wroot)
    sheet["hp"] = sheet["max_hp"] - 3
    worldfs.write_yaml(worldfs.state(wroot, "party/pc-borin"), sheet)
    combat.apply_heal(wroot, "pc-borin", 3, source="potion")
    sheet = _sheet(wroot)
    assert sheet["hp"] == sheet["max_hp"] and sheet["wounds"] == []


def test_partial_heal_keeps_wounds(wroot):
    make_pc()
    combat.add_wound(wroot, "pc-borin", "arrow in the leg")
    sheet = _sheet(wroot)
    sheet["hp"] = 1
    worldfs.write_yaml(worldfs.state(wroot, "party/pc-borin"), sheet)
    combat.apply_heal(wroot, "pc-borin", 1, source="potion")
    sheet = _sheet(wroot)
    assert sheet["hp"] < sheet["max_hp"] and len(sheet["wounds"]) == 1
