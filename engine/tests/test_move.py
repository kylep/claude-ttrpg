import json

from typer.testing import CliRunner

from ttrpg_engine import worldfs
from ttrpg_engine.cli import app
from test_attack import setup_fight

runner = CliRunner()


def test_move_ok_and_updates_position(wroot):
    setup_fight(wroot)                       # pc-borin at [10,3], speed 5 (dwarf)
    res = runner.invoke(app, ["move", "--actor", "pc-borin", "--to", "10,1"])
    assert res.exit_code == 0, res.stdout
    data = json.loads(res.stdout)
    assert data["to"] == [10, 1] and data["cost"] == 2
    enc = worldfs.read_yaml(wroot / "state" / "encounter.yaml")
    assert enc["positions"]["pc-borin"] == [10, 1]


def test_move_too_far_rejected(wroot):
    setup_fight(wroot)
    res = runner.invoke(app, ["move", "--actor", "pc-borin", "--to", "0,0"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "too_far"


def test_move_into_wall_rejected_difficult_costs_extra(wroot):
    setup_fight(wroot)
    # Test difficult terrain first (from original [10,3])
    # Chebyshev: max(|10-8|, |3-5|) = max(2, 2) = 2, +1 for difficult = cost 3
    res = runner.invoke(app, ["move", "--actor", "pc-borin", "--to", "8,5"])
    assert res.exit_code == 0
    assert json.loads(res.stdout)["cost"] == 3

    # Reset PC position to [10,3] for wall rejection test
    enc = worldfs.read_yaml(wroot / "state" / "encounter.yaml")
    enc["positions"]["pc-borin"] = [10, 3]
    worldfs.write_yaml(wroot / "state" / "encounter.yaml", enc)

    # Move PC closer to wall using --force (to test wall rejection)
    # From [10,3] to [5,2] is chebyshev 5, within speed 5
    res = runner.invoke(app, ["move", "--actor", "pc-borin", "--to", "5,2", "--force"])
    assert res.exit_code == 0

    # Now try to move into wall [4,1] from nearby (should be rejected with "blocked")
    # From [5,2] to [4,1] is chebyshev 1, within speed, but [4,1] is a wall
    res = runner.invoke(app, ["move", "--actor", "pc-borin", "--to", "4,1"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "blocked"


def test_force_ignores_cost(wroot):
    setup_fight(wroot)
    res = runner.invoke(app, ["move", "--actor", "pc-borin", "--to", "0,0", "--force"])
    assert res.exit_code == 0
