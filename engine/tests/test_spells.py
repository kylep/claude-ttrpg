import json
import random

from typer.testing import CliRunner

from ttrpg_engine import combat, spells, worldfs
from ttrpg_engine.cli import app
from conftest import make_pc
from test_attack import fixed

runner = CliRunner()

CLERIC = dict(name="Mira", cls="cleric", race="human",
              assign="WIS=15,CON=14,STR=13,DEX=12,INT=10,CHA=8",
              skills="insight,medicine")


def test_cure_wounds_consumes_slot_and_heals(wroot):
    make_pc(**CLERIC)
    combat.apply_damage(wroot, "pc-mira", 5, source="test")
    res = runner.invoke(app, ["--seed", "4", "cast", "--caster", "pc-mira",
                              "--spell", "cure_wounds", "--target", "pc-mira"])
    assert res.exit_code == 0, res.stdout
    data = json.loads(res.stdout)
    assert data["healed"] >= 1 + 3                     # 1d8 + WIS mod (16 -> +3)
    sheet = worldfs.read_yaml(wroot / "state" / "party" / "pc-mira.yaml")
    assert sheet["spell_slots"][1]["current"] == 1


def test_no_slots_left_fails(wroot):
    make_pc(**CLERIC)
    for _ in range(2):
        runner.invoke(app, ["cast", "--caster", "pc-mira", "--spell", "cure_wounds"])
    res = runner.invoke(app, ["cast", "--caster", "pc-mira", "--spell", "cure_wounds"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "no_slots"


def test_save_spell_damage_and_on_save_none(wroot):
    make_pc(**CLERIC)
    res = runner.invoke(app, ["--seed", "9", "encounter", "start",
                              "maps/encounters/skirmish.yaml"])
    assert res.exit_code == 0
    r = spells.cast(wroot, worldfs.load_game_for(wroot), "pc-mira", "sacred_flame",
                    "goblin-1", roll_fn=fixed(1), rng=random.Random(1))
    assert r["save"]["success"] is False               # nat 1 + DEX mod 2 = 3 < DC 13
    assert r["damage"] >= 1
    r2 = spells.cast(wroot, worldfs.load_game_for(wroot), "pc-mira", "sacred_flame",
                     "goblin-1", roll_fn=fixed(20), rng=random.Random(1))
    assert r2["save"]["success"] is True and r2["damage"] == 0


def test_unknown_spell_fails(wroot):
    make_pc(**CLERIC)
    res = runner.invoke(app, ["cast", "--caster", "pc-mira", "--spell", "fireball"])
    assert json.loads(res.stdout)["error"]["code"] == "unknown_spell"


def test_out_of_range_cast_does_not_burn_slot(wroot):
    make_pc(**CLERIC)
    res = runner.invoke(app, ["--seed", "9", "encounter", "start",
                              "maps/encounters/skirmish.yaml"])
    assert res.exit_code == 0, res.stdout
    res = runner.invoke(app, ["cast", "--caster", "pc-mira", "--spell", "cure_wounds",
                              "--target", "goblin-1"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "out_of_range"
    sheet = worldfs.read_yaml(wroot / "state" / "party" / "pc-mira.yaml")
    assert sheet["spell_slots"][1]["current"] == 2   # slot NOT burned
