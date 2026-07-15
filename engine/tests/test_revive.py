import json

from typer.testing import CliRunner

from ttrpg_engine import combat, worldfs
from ttrpg_engine.cli import app
from conftest import make_pc
from test_attack import fixed

runner = CliRunner()


def _sheet(wroot, pc):
    return worldfs.read_yaml(wroot / "state" / "party" / f"{pc}.yaml")


def _kill(wroot, pc):
    combat.apply_damage(wroot, pc, 999, source="test")   # -> 0 hp, dying/unconscious
    for _ in range(3):
        combat.death_save(wroot, pc, roll_fn=fixed(2))    # three fails -> dead
    assert "dead" in {e["name"] for e in _sheet(wroot, pc)["effects"]}


def test_revive_restores_dead_pc_weakened(wroot):
    pc = make_pc()
    _kill(wroot, pc)
    res = runner.invoke(app, ["revive", "--actor", pc])
    assert res.exit_code == 0, res.stdout
    data = json.loads(res.stdout)
    assert data["hp"] == 1
    names = {e["name"] for e in _sheet(wroot, pc)["effects"]}
    assert not ({"dead", "dying", "unconscious"} & names)   # all cleared
    assert "weakened" in names                              # comes back with the toll
    assert "death_saves" not in _sheet(wroot, pc)


def test_revive_hp_option(wroot):
    pc = make_pc()
    _kill(wroot, pc)
    res = runner.invoke(app, ["revive", "--actor", pc, "--hp", "5"])
    assert json.loads(res.stdout)["hp"] == 5


def test_revive_rejects_living_pc(wroot):
    pc = make_pc()
    res = runner.invoke(app, ["revive", "--actor", pc])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "not_dead"


def test_weakened_gives_disadvantage(wroot):
    pc = make_pc()
    _kill(wroot, pc)
    runner.invoke(app, ["revive", "--actor", pc])
    dis = combat.self_dis_conditions(wroot, None, pc, _sheet(wroot, pc))
    assert "weakened" in dis                                # rolls at disadvantage


def test_long_rest_clears_weakened(wroot):
    pc = make_pc()
    _kill(wroot, pc)
    runner.invoke(app, ["revive", "--actor", pc])
    res = runner.invoke(app, ["rest", "--type", "long"])
    assert res.exit_code == 0, res.stdout
    assert "weakened" not in {e["name"] for e in _sheet(wroot, pc)["effects"]}
