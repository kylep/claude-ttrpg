import json

from typer.testing import CliRunner

from ttrpg_engine import worldfs
from ttrpg_engine.cli import app
from conftest import make_pc

runner = CliRunner()


def _emit(res):
    assert res.exit_code == 0, res.stdout
    return json.loads(res.stdout)


def test_toggle_persists_and_status_reflects_it(wroot):
    # default: off
    assert _emit(runner.invoke(app, ["dice", "status"])) == {"manual_dice": False}

    on = _emit(runner.invoke(app, ["dice", "manual", "--on"]))
    assert on == {"manual_dice": True}
    # persisted into session.yaml
    sess = worldfs.read_yaml(worldfs.state(wroot, "session"))
    assert sess["manual_dice"] is True
    assert _emit(runner.invoke(app, ["dice", "status"])) == {"manual_dice": True}

    off = _emit(runner.invoke(app, ["dice", "manual", "--off"]))
    assert off == {"manual_dice": False}
    assert _emit(runner.invoke(app, ["dice", "status"])) == {"manual_dice": False}


def test_dice_manual_requires_exactly_one_flag(wroot):
    res = runner.invoke(app, ["dice", "manual"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "bad_toggle"
    res = runner.invoke(app, ["dice", "manual", "--on", "--off"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "bad_toggle"


def test_roll_option_uses_supplied_natural_independent_of_seed(wroot):
    pc = make_pc()  # WIS 12 (+1), proficient perception (+2) => modifier 3
    # --roll wins even without manual mode, and is deterministic regardless of seed
    for seed in ("1", "2", "99"):
        data = _emit(runner.invoke(app, ["--seed", seed, "check", "--actor", pc,
                                         "--attr", "WIS", "--skill", "perception",
                                         "--dc", "12", "--roll", "15"]))
        assert data["natural"] == 15
        assert data["total"] == 18
        assert data["success"] is True


def test_manual_mode_check_without_roll_returns_payload(wroot):
    pc = make_pc()
    runner.invoke(app, ["dice", "manual", "--on"])
    data = _emit(runner.invoke(app, ["check", "--actor", pc, "--attr", "WIS",
                                     "--skill", "perception", "--dc", "12"]))
    mr = data["manual_roll"]
    assert mr["die"] == "d20"
    assert mr["count"] == 1
    assert mr["keep"] == "one"
    assert mr["modifier"] == 3
    assert mr["label"] == "Perception check"
    assert "--roll" in mr["hint"]


def test_manual_mode_adv_dis_reflected_in_payload(wroot):
    pc = make_pc()
    runner.invoke(app, ["dice", "manual", "--on"])
    adv = _emit(runner.invoke(app, ["check", "--actor", pc, "--attr", "STR",
                                    "--dc", "10", "--adv"]))["manual_roll"]
    assert adv["count"] == 2 and adv["keep"] == "high"
    dis = _emit(runner.invoke(app, ["check", "--actor", pc, "--attr", "STR",
                                    "--dc", "10", "--dis"]))["manual_roll"]
    assert dis["count"] == 2 and dis["keep"] == "low"


def test_out_of_range_roll_is_rejected(wroot):
    pc = make_pc()
    res = runner.invoke(app, ["check", "--actor", pc, "--attr", "STR",
                              "--dc", "10", "--roll", "25"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "bad_roll"
    res = runner.invoke(app, ["check", "--actor", pc, "--attr", "STR",
                              "--dc", "10", "--roll", "0"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "bad_roll"


def _make_dying_pc(wroot):
    from ttrpg_engine import combat
    pc = make_pc()
    combat.apply_damage(wroot, pc, 999, source="test")  # drop to dying
    sheet = worldfs.read_yaml(worldfs.state(wroot, f"party/{pc}"))
    assert "dying" in {e["name"] for e in sheet["effects"]}
    return pc


def test_manual_deathsave_without_roll_does_not_mutate(wroot):
    pc = _make_dying_pc(wroot)
    before = worldfs.read_yaml(worldfs.state(wroot, f"party/{pc}"))
    runner.invoke(app, ["dice", "manual", "--on"])
    data = _emit(runner.invoke(app, ["deathsave", "--actor", pc]))
    assert data["manual_roll"]["label"] == "Death save"
    after = worldfs.read_yaml(worldfs.state(wroot, f"party/{pc}"))
    assert after == before  # no death_saves recorded, nothing persisted

    # supplying --roll then applies it
    applied = _emit(runner.invoke(app, ["deathsave", "--actor", pc, "--roll", "18"]))
    assert applied["natural"] == 18
    assert applied["result"] == "success"
    after2 = worldfs.read_yaml(worldfs.state(wroot, f"party/{pc}"))
    assert after2["death_saves"]["successes"] == 1
