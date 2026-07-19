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


def test_check_reports_crit_and_fumble(wroot):
    from ttrpg_engine import checks
    pc = make_pc()
    crit = checks.run(wroot, pc, "STR", 10, skill=None, adv=False, dis=False,
                      roll_fn=lambda m, a, d: (20, 20 + m))
    assert crit["crit"] == "hit"
    fumble = checks.run(wroot, pc, "STR", 10, skill=None, adv=False, dis=False,
                        roll_fn=lambda m, a, d: (1, 1 + m))
    assert fumble["crit"] == "fumble"


def test_check_forwards_adv_dis_flags(wroot):
    from ttrpg_engine import checks
    pc = make_pc()
    seen = {}

    def spy(mod, adv, dis):
        seen["adv"], seen["dis"] = adv, dis
        return 10, 10 + mod

    checks.run(wroot, pc, "STR", 10, skill=None, adv=True, dis=False, roll_fn=spy)
    assert seen == {"adv": True, "dis": False}
    checks.run(wroot, pc, "STR", 10, skill=None, adv=False, dis=True, roll_fn=spy)
    assert seen == {"adv": False, "dis": True}


def test_check_requires_item_present_runs(wroot):
    pc = make_pc()  # dwarf fighter, carries longsword + chain_mail
    res = runner.invoke(app, ["--seed", "1", "check", "--actor", pc, "--attr", "DEX",
                              "--dc", "5", "--requires-item", "longsword"])
    assert res.exit_code == 0, res.stdout
    assert "error" not in json.loads(res.stdout)


def test_check_requires_missing_item_blocked(wroot):
    pc = make_pc()  # does not carry thieves_tools
    res = runner.invoke(app, ["check", "--actor", pc, "--attr", "DEX", "--dc", "5",
                              "--requires-item", "thieves_tools"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "needs_item"
