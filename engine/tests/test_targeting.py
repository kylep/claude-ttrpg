import json
import random

from typer.testing import CliRunner

from ttrpg_engine import combat, spells, worldfs
from ttrpg_engine.cli import app
from ttrpg_engine.errors import EngineError
from conftest import make_pc
from test_attack import fixed, setup_fight
from test_spells import CLERIC, _level_cleric_to_3

runner = CliRunner()


# ---------------------------------------------------------------------------
# Mechanism 1: attack kind + ranged-in-melee disadvantage
# ---------------------------------------------------------------------------

def test_attack_kind_defaults():
    assert combat.attack_kind({"range": 1}) == "melee"
    assert combat.attack_kind({}) == "melee"                       # default range 1
    assert combat.attack_kind({"range": 2}) == "ranged"
    assert combat.attack_kind({"range": 8}) == "ranged"
    assert combat.attack_kind({"range": 2, "kind": "melee"}) == "melee"   # reach weapon
    assert combat.attack_kind({"range": 1, "kind": "ranged"}) == "ranged"


def test_ranged_attack_adjacent_hostile_triggers_disadvantage(wroot):
    setup_fight(wroot)                                             # pc-borin at [10,3]
    runner.invoke(app, ["item", "add", "--actor", "pc-borin", "--item", "shortbow"])
    res = runner.invoke(app, ["equip", "--actor", "pc-borin", "--item", "shortbow"])
    assert res.exit_code == 0, res.stdout

    calls = []

    def spy(mod, adv, dis):
        calls.append((adv, dis))
        return 15, 15 + mod

    # adjacent to both goblins -> disadvantage forced even though caller passed none
    r = combat.attack(wroot, "pc-borin", "goblin-1", attack_name="shortbow",
                      adv=False, dis=False, roll_fn=spy, rng=random.Random(1))
    assert r["ranged_in_melee"] is True
    assert calls[-1] == (False, True)

    # move out of melee range of every hostile, but still within shortbow range (8)
    enc = worldfs.read_yaml(wroot / "state" / "encounter.yaml")
    enc["positions"]["pc-borin"] = [4, 3]
    worldfs.write_yaml(wroot / "state" / "encounter.yaml", enc)
    r2 = combat.attack(wroot, "pc-borin", "goblin-1", attack_name="shortbow",
                       adv=False, dis=False, roll_fn=spy, rng=random.Random(1))
    assert "ranged_in_melee" not in r2
    assert calls[-1] == (False, False)


def test_melee_reach_weapon_hits_at_range_2_without_ranged_in_melee(wroot):
    setup_fight(wroot)
    runner.invoke(app, ["item", "add", "--actor", "pc-borin", "--item", "spear"])
    res = runner.invoke(app, ["equip", "--actor", "pc-borin", "--item", "spear"])
    assert res.exit_code == 0, res.stdout

    enc = worldfs.read_yaml(wroot / "state" / "encounter.yaml")
    enc["positions"]["pc-borin"] = [11, 2]                          # chebyshev 2 from goblin-1 [9,4]
    worldfs.write_yaml(wroot / "state" / "encounter.yaml", enc)

    r = combat.attack(wroot, "pc-borin", "goblin-1", attack_name="spear",
                      adv=False, dis=False, roll_fn=fixed(15), rng=random.Random(1))
    assert r["hit"] is True                                        # range 2 accepted, not out_of_range
    assert "ranged_in_melee" not in r


def test_spell_attack_roll_gets_ranged_in_melee_disadvantage(wroot):
    make_pc(**CLERIC)
    runner.invoke(app, ["xp", "grant", "--amount", "9999", "--reason", "test"])
    res = runner.invoke(app, ["--seed", "1", "level", "up", "--actor", "pc-mira"])
    assert res.exit_code == 0, res.stdout
    sheet = worldfs.read_yaml(wroot / "state" / "party" / "pc-mira.yaml")
    assert "fire_dart" in sheet["spells_known"]

    res = runner.invoke(app, ["--seed", "9", "encounter", "start",
                              "maps/encounters/skirmish.yaml"])
    assert res.exit_code == 0, res.stdout
    enc = worldfs.read_yaml(wroot / "state" / "encounter.yaml")
    enc["positions"]["pc-mira"] = [10, 3]                           # adjacent to both goblins
    worldfs.write_yaml(wroot / "state" / "encounter.yaml", enc)

    calls = []

    def spy(mod, adv, dis):
        calls.append((adv, dis))
        return 15, 15 + mod

    g = worldfs.load_game_for(wroot)
    r = spells.cast(wroot, g, "pc-mira", "fire_dart", "goblin-1", roll_fn=spy, rng=random.Random(1))
    assert r.get("ranged_in_melee") is True
    assert calls[-1] == (False, True)


# ---------------------------------------------------------------------------
# Mechanism 2: flying / aloft
# ---------------------------------------------------------------------------

def test_ascend_requires_flying_capability(wroot):
    setup_fight(wroot)
    res = runner.invoke(app, ["ascend", "--actor", "pc-borin"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "cannot_fly"


def test_ascend_via_flying_effect_then_land_and_move_ignores_difficult_terrain(wroot):
    setup_fight(wroot)                                             # pc-borin at [10,3], speed 5
    combat.set_effect(wroot, "pc-borin", "flying", -1)
    res = runner.invoke(app, ["ascend", "--actor", "pc-borin"])
    assert res.exit_code == 0, res.stdout
    assert json.loads(res.stdout) == {"actor": "pc-borin", "aloft": True}

    # [10,3] -> [8,5]: chebyshev 2, [8,5] is difficult terrain (grounded cost would be 3)
    res = runner.invoke(app, ["move", "--actor", "pc-borin", "--to", "8,5"])
    assert res.exit_code == 0, res.stdout
    assert json.loads(res.stdout)["cost"] == 2

    res = runner.invoke(app, ["land", "--actor", "pc-borin"])
    assert res.exit_code == 0, res.stdout
    assert json.loads(res.stdout) == {"actor": "pc-borin", "aloft": False}


def test_flying_monster_blocks_melee_but_allows_ranged(wroot):
    make_pc()
    runner.invoke(app, ["item", "add", "--actor", "pc-borin", "--item", "shortbow"])
    runner.invoke(app, ["equip", "--actor", "pc-borin", "--item", "shortbow"])
    res = runner.invoke(app, ["--seed", "5", "encounter", "start",
                              "maps/encounters/skyfight.yaml"])
    assert res.exit_code == 0, res.stdout
    combat.ascend(wroot, "giant_bat-1")

    enc = worldfs.read_yaml(wroot / "state" / "encounter.yaml")
    enc["positions"]["pc-borin"] = [6, 2]                           # chebyshev 1 from giant_bat-1 [6,3]
    worldfs.write_yaml(wroot / "state" / "encounter.yaml", enc)

    try:
        combat.attack(wroot, "pc-borin", "giant_bat-1", attack_name="longsword",
                     adv=False, dis=False, roll_fn=fixed(15), rng=random.Random(1))
        raise AssertionError("melee should be unreachable against an airborne target")
    except EngineError as e:
        assert e.code == "unreachable"

    r = combat.attack(wroot, "pc-borin", "giant_bat-1", attack_name="shortbow",
                      adv=False, dis=False, roll_fn=fixed(15), rng=random.Random(1))
    assert "hit" in r                                              # no exception: ranged ignores plane


def test_flying_monster_can_be_hit_by_save_spell(wroot):
    make_pc(**CLERIC)
    res = runner.invoke(app, ["--seed", "5", "encounter", "start",
                              "maps/encounters/skyfight.yaml"])
    assert res.exit_code == 0, res.stdout
    combat.ascend(wroot, "giant_bat-1")

    enc = worldfs.read_yaml(wroot / "state" / "encounter.yaml")
    enc["positions"]["pc-mira"] = [6, 2]
    worldfs.write_yaml(wroot / "state" / "encounter.yaml", enc)

    g = worldfs.load_game_for(wroot)
    r = spells.cast(wroot, g, "pc-mira", "sacred_flame", "giant_bat-1",
                    roll_fn=fixed(1), rng=random.Random(1))
    assert r["save"]["success"] is False
    assert r["damage"] >= 1


def test_aloft_attacker_vs_grounded_target_melee_unreachable(wroot):
    setup_fight(wroot)                                             # pc-borin adjacent to goblins
    enc = worldfs.read_yaml(wroot / "state" / "encounter.yaml")
    enc.setdefault("aloft", {})["pc-borin"] = True
    worldfs.write_yaml(wroot / "state" / "encounter.yaml", enc)
    try:
        combat.attack(wroot, "pc-borin", "goblin-1", attack_name="longsword",
                     adv=False, dis=False, roll_fn=fixed(15), rng=random.Random(1))
        raise AssertionError("should have raised unreachable")
    except EngineError as e:
        assert e.code == "unreachable"
        assert "grounded" in e.message


# ---------------------------------------------------------------------------
# Mechanism 3: AOE spells
# ---------------------------------------------------------------------------

def test_aoe_hits_radius_two_affected_one_untouched(wroot):
    _level_cleric_to_3(wroot)
    res = runner.invoke(app, ["--seed", "9", "encounter", "start",
                              "maps/encounters/swarm.yaml"])
    assert res.exit_code == 0, res.stdout
    g = worldfs.load_game_for(wroot)
    r = spells.cast(wroot, g, "pc-mira", "flame_wave", None,
                    roll_fn=fixed(1), rng=random.Random(1), at=(5, 4))
    ids = {t["id"] for t in r["targets"]}
    assert ids == {"goblin-1", "goblin-2"}                          # goblin-3 is out of radius
    assert all(t["damage"] > 0 for t in r["targets"])
    assert all("save" in t for t in r["targets"])                   # each rolled its own save

    enc = worldfs.read_yaml(wroot / "state" / "encounter.yaml")
    assert enc["monsters"]["goblin-3"]["hp"] == 7                   # untouched


def test_aoe_friendly_fire(wroot):
    _level_cleric_to_3(wroot)
    make_pc()                                                       # pc-borin, same location
    res = runner.invoke(app, ["--seed", "9", "encounter", "start",
                              "maps/encounters/swarm.yaml", "--pcs", "pc-borin,pc-mira"])
    assert res.exit_code == 0, res.stdout
    enc = worldfs.read_yaml(wroot / "state" / "encounter.yaml")
    enc["positions"]["pc-borin"] = [5, 5]                            # chebyshev 1 from cell (5,4)
    worldfs.write_yaml(wroot / "state" / "encounter.yaml", enc)

    g = worldfs.load_game_for(wroot)
    r = spells.cast(wroot, g, "pc-mira", "flame_wave", None,
                    roll_fn=fixed(1), rng=random.Random(2), at=(5, 4))
    ids = {t["id"] for t in r["targets"]}
    assert "pc-borin" in ids

    sheet = worldfs.read_yaml(wroot / "state" / "party" / "pc-borin.yaml")
    assert sheet["hp"] < sheet["max_hp"]


def test_area_spell_rejects_target_argument(wroot):
    _level_cleric_to_3(wroot)
    runner.invoke(app, ["--seed", "9", "encounter", "start", "maps/encounters/swarm.yaml"])
    g = worldfs.load_game_for(wroot)
    try:
        spells.cast(wroot, g, "pc-mira", "flame_wave", "goblin-1", roll_fn=fixed(1), rng=random.Random(1))
        raise AssertionError("should have raised")
    except EngineError as e:
        assert e.code == "area_needs_cell"


def test_area_spell_requires_at(wroot):
    _level_cleric_to_3(wroot)
    runner.invoke(app, ["--seed", "9", "encounter", "start", "maps/encounters/swarm.yaml"])
    g = worldfs.load_game_for(wroot)
    try:
        spells.cast(wroot, g, "pc-mira", "flame_wave", None, roll_fn=fixed(1), rng=random.Random(1))
        raise AssertionError("should have raised")
    except EngineError as e:
        assert e.code == "area_needs_cell"


def test_non_area_spell_rejects_at(wroot):
    make_pc(**CLERIC)
    runner.invoke(app, ["--seed", "9", "encounter", "start", "maps/encounters/swarm.yaml"])
    g = worldfs.load_game_for(wroot)
    try:
        spells.cast(wroot, g, "pc-mira", "cure_wounds", None,
                   roll_fn=fixed(1), rng=random.Random(1), at=(5, 4))
        raise AssertionError("should have raised")
    except EngineError as e:
        assert e.code == "not_area"


def test_aoe_slot_consumed_once_and_not_on_range_failure(wroot):
    _level_cleric_to_3(wroot)
    runner.invoke(app, ["--seed", "9", "encounter", "start", "maps/encounters/swarm.yaml"])
    sheet = worldfs.read_yaml(wroot / "state" / "party" / "pc-mira.yaml")
    assert sheet["spell_slots"][2]["current"] == 1

    g = worldfs.load_game_for(wroot)
    try:
        spells.cast(wroot, g, "pc-mira", "flame_wave", None,
                   roll_fn=fixed(1), rng=random.Random(1), at=(100, 100))
        raise AssertionError("should have raised out_of_range")
    except EngineError as e:
        assert e.code == "out_of_range"
    sheet = worldfs.read_yaml(wroot / "state" / "party" / "pc-mira.yaml")
    assert sheet["spell_slots"][2]["current"] == 1                  # not spent on failed range check

    spells.cast(wroot, g, "pc-mira", "flame_wave", None,
               roll_fn=fixed(1), rng=random.Random(2), at=(5, 4))
    sheet = worldfs.read_yaml(wroot / "state" / "party" / "pc-mira.yaml")
    assert sheet["spell_slots"][2]["current"] == 0                  # spent exactly once


def test_cli_cast_at_cell(wroot):
    _level_cleric_to_3(wroot)
    runner.invoke(app, ["--seed", "9", "encounter", "start", "maps/encounters/swarm.yaml"])
    res = runner.invoke(app, ["--seed", "1", "cast", "--caster", "pc-mira",
                              "--spell", "flame_wave", "--at", "5,4"])
    assert res.exit_code == 0, res.stdout
    data = json.loads(res.stdout)
    assert data["cell"] == [5, 4]
    assert {"goblin-1", "goblin-2"} <= {t["id"] for t in data["targets"]}
