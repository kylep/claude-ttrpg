import json

from typer.testing import CliRunner

from ttrpg_engine import worldfs
from ttrpg_engine.cli import app
from conftest import make_pc

runner = CliRunner()


def _sheet(wroot, pc):
    return worldfs.read_yaml(wroot / "state" / "party" / f"{pc}.yaml")


def start_fight(wroot):
    pc = make_pc()
    res = runner.invoke(app, ["--seed", "5", "encounter", "start",
                              "maps/encounters/skirmish.yaml"])
    assert res.exit_code == 0, res.stdout
    return pc


def test_equip_armor_mid_encounter_blocked(wroot):
    pc = start_fight(wroot)
    runner.invoke(app, ["item", "add", "--actor", pc, "--item", "leather_armor"])
    res = runner.invoke(app, ["equip", "--actor", pc, "--item", "leather_armor"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "no_time"


def test_unequip_armor_mid_encounter_blocked(wroot):
    pc = start_fight(wroot)
    res = runner.invoke(app, ["unequip", "--actor", pc, "--item", "chain_mail"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "no_time"


def test_first_non_armor_swap_succeeds_second_blocked_same_round(wroot):
    pc = start_fight(wroot)
    runner.invoke(app, ["item", "add", "--actor", pc, "--item", "dagger"])
    res = runner.invoke(app, ["equip", "--actor", pc, "--item", "dagger"])
    assert res.exit_code == 0, res.stdout

    res2 = runner.invoke(app, ["unequip", "--actor", pc, "--item", "dagger"])
    assert res2.exit_code == 1
    assert json.loads(res2.stdout)["error"]["code"] == "action_spent"


def test_swap_allowed_again_after_full_round(wroot):
    pc = start_fight(wroot)
    runner.invoke(app, ["item", "add", "--actor", pc, "--item", "dagger"])
    res = runner.invoke(app, ["equip", "--actor", pc, "--item", "dagger"])
    assert res.exit_code == 0, res.stdout

    # fixture skirmish has 3 combatants (pc-borin, goblin-1, goblin-2) -> 3
    # `encounter next` calls cycle exactly one full round.
    for _ in range(3):
        r = runner.invoke(app, ["encounter", "next"])
        assert r.exit_code == 0, r.stdout

    res2 = runner.invoke(app, ["unequip", "--actor", pc, "--item", "dagger"])
    assert res2.exit_code == 0, res2.stdout


def test_force_bypasses_armor_block_and_marks_forced(wroot):
    pc = start_fight(wroot)
    res = runner.invoke(app, ["unequip", "--actor", pc, "--item", "chain_mail", "--force"])
    assert res.exit_code == 0, res.stdout
    payload = json.loads(res.stdout)
    assert payload["forced"] is True


def test_force_bypasses_action_spent_block(wroot):
    pc = start_fight(wroot)
    runner.invoke(app, ["item", "add", "--actor", pc, "--item", "dagger"])
    res1 = runner.invoke(app, ["equip", "--actor", pc, "--item", "dagger"])
    assert res1.exit_code == 0, res1.stdout
    assert json.loads(res1.stdout)["forced"] is False

    res2 = runner.invoke(app, ["unequip", "--actor", pc, "--item", "dagger", "--force"])
    assert res2.exit_code == 0, res2.stdout
    assert json.loads(res2.stdout)["forced"] is True


def test_no_restriction_outside_encounter(wroot):
    pc = make_pc()
    runner.invoke(app, ["item", "add", "--actor", pc, "--item", "dagger"])
    for _ in range(3):
        res = runner.invoke(app, ["equip", "--actor", pc, "--item", "dagger"])
        assert res.exit_code == 0, res.stdout
        res = runner.invoke(app, ["unequip", "--actor", pc, "--item", "dagger"])
        assert res.exit_code == 0, res.stdout
    assert "gear_actions" not in _sheet(wroot, pc)
