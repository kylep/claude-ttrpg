import json
import random

from typer.testing import CliRunner

from ttrpg_engine import combat, dice, spells, worldfs
from ttrpg_engine.cli import app
from ttrpg_engine.errors import EngineError
from conftest import make_pc
from test_attack import fixed

runner = CliRunner()

CLERIC = dict(name="Mira", cls="cleric", race="human",
              assign="WIS=15,CON=14,STR=13,DEX=12,INT=10,CHA=8",
              skills="insight,medicine")


def _level_cleric_to_3(wroot):
    make_pc(**CLERIC)
    runner.invoke(app, ["xp", "grant", "--amount", "9999", "--reason", "test"])
    runner.invoke(app, ["--seed", "1", "level", "up", "--actor", "pc-mira"])
    res = runner.invoke(app, ["--seed", "1", "level", "up", "--actor", "pc-mira"])
    assert res.exit_code == 0, res.stdout
    sheet = worldfs.read_yaml(wroot / "state" / "party" / "pc-mira.yaml")
    assert sheet["level"] == 3
    return sheet


def _start_encounter_adjacent_to_goblin(wroot):
    res = runner.invoke(app, ["--seed", "9", "encounter", "start",
                              "maps/encounters/skirmish.yaml"])
    assert res.exit_code == 0, res.stdout
    # holy_burst has range 6; pull pc-mira next to goblin-1 (default spawn is 8 away)
    enc = worldfs.read_yaml(wroot / "state" / "encounter.yaml")
    enc["positions"]["pc-mira"] = [9, 5]
    worldfs.write_yaml(wroot / "state" / "encounter.yaml", enc)


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


def test_holy_burst_full_damage_on_failed_save(wroot):
    _level_cleric_to_3(wroot)
    _start_encounter_adjacent_to_goblin(wroot)
    g = worldfs.load_game_for(wroot)
    expected = dice.roll("3d6", random.Random(1)).total
    r = spells.cast(wroot, g, "pc-mira", "holy_burst", "goblin-1",
                    roll_fn=fixed(1), rng=random.Random(1))
    assert r["save"]["success"] is False                # nat 1 + DEX mod 2 = 3 < DC 13
    assert r["damage"] == expected


def test_holy_burst_half_damage_on_successful_save(wroot):
    _level_cleric_to_3(wroot)
    _start_encounter_adjacent_to_goblin(wroot)
    g = worldfs.load_game_for(wroot)
    full = dice.roll("3d6", random.Random(1)).total
    r = spells.cast(wroot, g, "pc-mira", "holy_burst", "goblin-1",
                    roll_fn=fixed(20), rng=random.Random(1))
    assert r["save"]["success"] is True                  # nat 20 + DEX mod 2 = 22 >= DC 13
    assert r["damage"] == max(1, full // 2)


def test_holy_burst_consumes_level2_slot_only(wroot):
    sheet = _level_cleric_to_3(wroot)
    assert sheet["spell_slots"][1]["current"] == 4
    assert sheet["spell_slots"][2]["current"] == 1
    _start_encounter_adjacent_to_goblin(wroot)
    g = worldfs.load_game_for(wroot)
    spells.cast(wroot, g, "pc-mira", "holy_burst", "goblin-1",
               roll_fn=fixed(1), rng=random.Random(2))
    sheet = worldfs.read_yaml(wroot / "state" / "party" / "pc-mira.yaml")
    assert sheet["spell_slots"][2]["current"] == 0       # L2 slot consumed
    assert sheet["spell_slots"][1]["current"] == 4       # L1 slots untouched


def test_holy_burst_no_slots_left_fails(wroot):
    _level_cleric_to_3(wroot)
    _start_encounter_adjacent_to_goblin(wroot)
    g = worldfs.load_game_for(wroot)
    spells.cast(wroot, g, "pc-mira", "holy_burst", "goblin-1",
               roll_fn=fixed(1), rng=random.Random(2))   # burns the only L2 slot
    try:
        spells.cast(wroot, g, "pc-mira", "holy_burst", "goblin-1",
                   roll_fn=fixed(1), rng=random.Random(3))
        raise AssertionError("should have raised")
    except EngineError as e:
        assert e.code == "no_slots"


def test_attack_spell_doubles_damage_on_crit(wroot):
    # regression: spell attack rolls used to skip crit doubling that weapon
    # attacks got. fire_dart is an attack-resolve cantrip (1d6) the cleric
    # learns at level 2.
    _level_cleric_to_3(wroot)
    _start_encounter_adjacent_to_goblin(wroot)
    g = worldfs.load_game_for(wroot)
    enc = worldfs.read_yaml(wroot / "state" / "encounter.yaml")
    enc["monsters"]["goblin-1"]["hp"] = 100          # avoid damage capping at low HP
    enc["monsters"]["goblin-1"]["max_hp"] = 100
    worldfs.write_yaml(wroot / "state" / "encounter.yaml", enc)

    crit = spells.cast(wroot, g, "pc-mira", "fire_dart", "goblin-1",
                       roll_fn=fixed(20), rng=random.Random(3))
    assert crit["attack"]["crit"] == "hit"
    assert crit["damage"] == combat.roll_damage("1d6", random.Random(3), "hit")

    worldfs.write_yaml(wroot / "state" / "encounter.yaml", enc)   # reset HP
    plain = spells.cast(wroot, g, "pc-mira", "fire_dart", "goblin-1",
                        roll_fn=fixed(15), rng=random.Random(3))
    assert plain["attack"]["crit"] is None
    assert plain["damage"] == combat.roll_damage("1d6", random.Random(3), None)
    assert crit["damage"] > plain["damage"]           # doubling actually happened


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
