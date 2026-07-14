import json
import random

from typer.testing import CliRunner

from ttrpg_engine import combat, grid, spells, worldfs
from ttrpg_engine.cli import app
from ttrpg_engine.errors import EngineError
from conftest import make_pc
from test_attack import fixed, setup_fight
from test_spells import CLERIC, _level_cleric_to_3

runner = CliRunner()

ROGUE = dict(name="Sly", cls="rogue", race="human",
             assign="DEX=15,STR=14,CON=13,WIS=12,INT=10,CHA=8",
             skills="stealth,acrobatics")


def spy():
    calls = []

    def fn(mod, adv, dis):
        calls.append((adv, dis))
        return 15, 15 + mod
    return fn, calls


def seq(*naturals):
    it = iter(naturals)

    def fn(mod, adv, dis):
        n = next(it)
        return n, n + mod
    return fn


def get_enc(wroot):
    return worldfs.read_yaml(wroot / "state" / "encounter.yaml")


def put_pos(wroot, cid, pos):
    enc = get_enc(wroot)
    enc["positions"][cid] = list(pos)
    worldfs.write_yaml(wroot / "state" / "encounter.yaml", enc)


def effects_of(wroot, enc, cid):
    if cid.startswith("pc-"):
        return combat.effect_names(worldfs.read_yaml(wroot / "state" / "party" / f"{cid}.yaml"))
    return combat.effect_names(get_enc(wroot)["monsters"][cid])


def start_hideout(wroot, pcs=None):
    args = ["--seed", "5", "encounter", "start", "maps/encounters/hideout.yaml"]
    if pcs:
        args += ["--pcs", pcs]
    res = runner.invoke(app, args)
    assert res.exit_code == 0, res.stdout


# ---------------------------------------------------------------------------
# Line of sight + path cost (grid unit tests)
# ---------------------------------------------------------------------------

SYNTH = {"grid": {"width": 10, "height": 6},
         "terrain": [{"type": "wall", "cells": [[4, 1], [4, 2], [4, 3]]},
                     {"type": "difficult", "cells": [[2, 1], [2, 2], [2, 3]]}],
         "positions": {}, "monsters": {}}


def test_line_of_sight_walls_block_and_symmetric():
    assert grid.line_of_sight(SYNTH, (1, 2), (2, 2))                 # adjacent
    assert not grid.line_of_sight(SYNTH, (1, 2), (7, 2))             # through wall
    assert not grid.line_of_sight(SYNTH, (7, 2), (1, 2))             # symmetric
    assert grid.line_of_sight(SYNTH, (1, 0), (7, 0))                 # over the gap row
    assert grid.line_of_sight(SYNTH, (4, 0), (4, 4)) is False        # down the wall column


def test_path_cost_terrain_walls_and_blockers():
    # difficult column [2,1..3]: crossing it costs +1, detouring costs more steps
    assert grid.path_cost(SYNTH, (1, 2), (3, 2)) == 3
    assert grid.path_cost(SYNTH, (1, 0), (3, 0)) == 2                # straight, no terrain
    assert grid.path_cost(SYNTH, (1, 2), (3, 2), ignore_terrain=True) == 2
    # wall column [4,1..3] forces a detour through row 0 or row 4
    assert grid.path_cost(SYNTH, (3, 2), (5, 2)) == 4
    # impassable ring -> unreachable
    ring = {(0, 1), (1, 1), (2, 1), (0, 3), (1, 3), (2, 3), (2, 2)}
    boxed = {**SYNTH, "terrain": [{"type": "wall", "cells": [list(c) for c in ring]}]}
    assert grid.path_cost(boxed, (1, 2), (5, 2)) is None
    # hostile-occupied cells can't be crossed: detour dips through difficult [2,2]
    assert grid.path_cost(SYNTH, (1, 0), (3, 0), impassable={(2, 0), (2, 1)}) == 5


# ---------------------------------------------------------------------------
# Conditions on attack rolls
# ---------------------------------------------------------------------------

def test_prone_target_melee_adv_ranged_dis(wroot):
    setup_fight(wroot)                                               # pc-borin at [10,3]
    combat.set_effect(wroot, "goblin-1", "prone", -1)
    fn, calls = spy()
    r = combat.attack(wroot, "pc-borin", "goblin-1", attack_name="longsword",
                      adv=False, dis=False, roll_fn=fn, rng=random.Random(1))
    assert calls[-1] == (True, False)
    assert "target_prone" in r["adv_from"]

    runner.invoke(app, ["item", "add", "--actor", "pc-borin", "--item", "shortbow"])
    runner.invoke(app, ["equip", "--actor", "pc-borin", "--item", "shortbow"])
    put_pos(wroot, "pc-borin", (4, 3))                               # out of melee, in bow range
    r = combat.attack(wroot, "pc-borin", "goblin-1", attack_name="shortbow",
                      adv=False, dis=False, roll_fn=fn, rng=random.Random(1))
    assert calls[-1] == (False, True)
    assert "target_prone" in r["dis_from"]


def test_prone_attacker_disadvantage(wroot):
    setup_fight(wroot)
    combat.set_effect(wroot, "pc-borin", "prone", -1)
    fn, calls = spy()
    r = combat.attack(wroot, "pc-borin", "goblin-1", attack_name="longsword",
                      adv=False, dis=False, roll_fn=fn, rng=random.Random(1))
    assert calls[-1] == (False, True)
    assert "attacker_prone" in r["dis_from"]


def test_restrained_and_unconscious(wroot):
    setup_fight(wroot)
    combat.set_effect(wroot, "goblin-1", "restrained", -1)
    fn, calls = spy()
    combat.attack(wroot, "pc-borin", "goblin-1", attack_name="longsword",
                  adv=False, dis=False, roll_fn=fn, rng=random.Random(1))
    assert calls[-1] == (True, False)                                # adv against restrained
    combat.attack(wroot, "goblin-1", "pc-borin", attack_name=None,
                  adv=False, dis=False, roll_fn=fn, rng=random.Random(1))
    assert calls[-1] == (False, True)                                # restrained attacks at dis
    res = runner.invoke(app, ["move", "--actor", "goblin-1", "--to", "8,4"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "held"

    combat.set_effect(wroot, "goblin-2", "unconscious", -1)
    r = combat.attack(wroot, "pc-borin", "goblin-2", attack_name="longsword",
                      adv=False, dis=False, roll_fn=fn, rng=random.Random(1))
    assert calls[-1] == (True, False)
    assert "target_unconscious" in r["adv_from"]


def test_attack_requires_line_of_sight(wroot):
    make_pc()
    runner.invoke(app, ["item", "add", "--actor", "pc-borin", "--item", "shortbow"])
    runner.invoke(app, ["equip", "--actor", "pc-borin", "--item", "shortbow"])
    start_hideout(wroot)                                             # pc at [2,3], wall at x=5
    res = runner.invoke(app, ["attack", "--attacker", "pc-borin", "--attack", "shortbow",
                              "--target", "goblin_archer-1"])        # [10,2]: dist 8, wall between
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "no_los"


# ---------------------------------------------------------------------------
# Movement: prone crawl, held, path around hostiles
# ---------------------------------------------------------------------------

def test_prone_crawl_doubles_cost(wroot):
    setup_fight(wroot)                                               # pc-borin [10,3], speed 5
    combat.set_effect(wroot, "pc-borin", "prone", -1)
    res = runner.invoke(app, ["move", "--actor", "pc-borin", "--to", "10,1"])
    assert res.exit_code == 0, res.stdout
    assert json.loads(res.stdout)["cost"] == 4                       # 2 steps, crawling


def test_stand_clears_prone(wroot):
    setup_fight(wroot)
    combat.set_effect(wroot, "pc-borin", "prone", -1)
    res = runner.invoke(app, ["stand", "--actor", "pc-borin"])
    assert res.exit_code == 0, res.stdout
    assert "prone" not in effects_of(wroot, None, "pc-borin")
    res = runner.invoke(app, ["stand", "--actor", "pc-borin"])
    assert json.loads(res.stdout)["error"]["code"] == "not_prone"


# ---------------------------------------------------------------------------
# Stealth: hide, sneak, get spotted, reveal on attack/cast
# ---------------------------------------------------------------------------

def test_hide_fails_in_plain_sight(wroot):
    make_pc()
    start_hideout(wroot)
    put_pos(wroot, "pc-borin", (6, 3))                               # east of the wall, seen by both
    try:
        combat.hide(wroot, worldfs.load_game_for(wroot), "pc-borin", roll_fn=fixed(15))
        raise AssertionError("should have raised seen")
    except EngineError as e:
        assert e.code == "seen"


def test_hide_sneak_and_ambush_with_advantage(wroot):
    make_pc(**ROGUE)
    runner.invoke(app, ["item", "add", "--actor", "pc-sly", "--item", "shortbow"])
    res = runner.invoke(app, ["equip", "--actor", "pc-sly", "--item", "shortbow"])
    assert res.exit_code == 0, res.stdout
    start_hideout(wroot)                                             # pc-sly at [2,3], concealed

    r = combat.hide(wroot, worldfs.load_game_for(wroot), "pc-sly", roll_fn=fixed(15))              # stealth 15+4=19
    assert r["hidden"] and r["stealth"] == 19
    assert "hidden" in effects_of(wroot, None, "pc-sly")

    # sneak around the wall into the open; stealth 19 beats passive perception 9
    res = runner.invoke(app, ["move", "--actor", "pc-sly", "--to", "6,3"])
    assert res.exit_code == 0, res.stdout
    assert "revealed_by" not in json.loads(res.stdout)
    assert "hidden" in effects_of(wroot, None, "pc-sly")

    fn, calls = spy()
    r = combat.attack(wroot, "pc-sly", "goblin-1", attack_name="shortbow",
                      adv=False, dis=False, roll_fn=fn, rng=random.Random(1))
    assert calls[-1] == (True, False)                                # ambush advantage
    assert r["revealed"] is True
    assert 1 <= r["sneak_attack"] <= 6                               # level 1 -> 1d6
    assert "hidden" not in effects_of(wroot, None, "pc-sly")
    assert "stealth" not in get_enc(wroot).get("stealth", {})


def test_low_stealth_gets_spotted_moving_into_view(wroot):
    make_pc(**ROGUE)
    start_hideout(wroot)
    combat.hide(wroot, worldfs.load_game_for(wroot), "pc-sly", roll_fn=fixed(1))                   # stealth 5 < passive 9
    res = runner.invoke(app, ["move", "--actor", "pc-sly", "--to", "6,3"])
    assert res.exit_code == 0, res.stdout
    assert json.loads(res.stdout)["revealed_by"] == ["goblin-1", "goblin_archer-1"]
    assert "hidden" not in effects_of(wroot, None, "pc-sly")


def test_hostile_moving_around_cover_spots_low_stealth(wroot):
    make_pc(**ROGUE)
    start_hideout(wroot)
    combat.hide(wroot, worldfs.load_game_for(wroot), "pc-sly", roll_fn=fixed(1))                   # stealth 5
    # goblin-1 walks north past the wall's end and can now see the spawn
    res = runner.invoke(app, ["move", "--actor", "goblin-1", "--to", "6,0"])
    assert res.exit_code == 0, res.stdout
    assert json.loads(res.stdout)["spotted"] == ["pc-sly"]
    assert "hidden" not in effects_of(wroot, None, "pc-sly")


def test_hostile_moving_around_cover_misses_high_stealth(wroot):
    make_pc(**ROGUE)
    start_hideout(wroot)
    combat.hide(wroot, worldfs.load_game_for(wroot), "pc-sly", roll_fn=fixed(15))                  # stealth 19 > passive 9
    res = runner.invoke(app, ["move", "--actor", "goblin-1", "--to", "6,0"])
    assert res.exit_code == 0, res.stdout
    assert "spotted" not in json.loads(res.stdout)
    assert "hidden" in effects_of(wroot, None, "pc-sly")


def test_hide_roll_modifiers(wroot):
    make_pc()                                                        # borin wears chain mail
    start_hideout(wroot)
    g = worldfs.load_game_for(wroot)
    fn, calls = spy()
    r = combat.hide(wroot, g, "pc-borin", roll_fn=fn)
    assert calls[-1] == (False, True)                                # noisy armor
    assert r["dis_from"] == ["noisy:chain_mail"]

    combat.set_effect(wroot, "pc-borin", "silent_step", -1)          # hush-charmed boots etc.
    r = combat.hide(wroot, g, "pc-borin", roll_fn=fn)
    assert calls[-1] == (True, True)                                 # cancels to a straight roll
    assert r["adv_from"] == ["silent_step"]

    runner.invoke(app, ["unequip", "--actor", "pc-borin", "--item", "chain_mail", "--force"])
    r = combat.hide(wroot, g, "pc-borin", roll_fn=fn)
    assert calls[-1] == (True, False)                                # silent and unarmored
    assert "dis_from" not in r


def test_cannot_hide_while_held(wroot):
    make_pc(**ROGUE)
    start_hideout(wroot)
    combat.set_effect(wroot, "pc-sly", "grappled", -1)
    try:
        combat.hide(wroot, worldfs.load_game_for(wroot), "pc-sly", roll_fn=fixed(15))
        raise AssertionError("should have raised held")
    except EngineError as e:
        assert e.code == "held"


def test_attacking_hidden_target_has_disadvantage(wroot):
    make_pc()
    start_hideout(wroot)
    combat.hide(wroot, worldfs.load_game_for(wroot), "pc-borin", roll_fn=fixed(15))
    put_pos(wroot, "goblin-1", (3, 3))                               # adjacent to hidden pc
    fn, calls = spy()
    r = combat.attack(wroot, "goblin-1", "pc-borin", attack_name=None,
                      adv=False, dis=False, roll_fn=fn, rng=random.Random(1))
    assert calls[-1] == (False, True)
    assert "target_hidden" in r["dis_from"]


def test_casting_reveals_hidden_caster_with_advantage(wroot):
    _level_cleric_to_3(wroot)                                        # pc-mira knows fire_dart
    start_hideout(wroot)
    combat.hide(wroot, worldfs.load_game_for(wroot), "pc-mira", roll_fn=fixed(15))
    res = runner.invoke(app, ["move", "--actor", "pc-mira", "--to", "6,3"])
    assert res.exit_code == 0, res.stdout
    fn, calls = spy()
    g = worldfs.load_game_for(wroot)
    r = spells.cast(wroot, g, "pc-mira", "fire_dart", "goblin-1",
                    roll_fn=fn, rng=random.Random(1))
    assert calls[-1] == (True, False)                                # hidden caster strikes with adv
    assert r["revealed"] is True
    assert "hidden" not in effects_of(wroot, None, "pc-mira")


def test_spell_requires_line_of_sight_and_keeps_slot(wroot):
    _level_cleric_to_3(wroot)
    start_hideout(wroot)                                             # pc-mira at [2,3]
    g = worldfs.load_game_for(wroot)
    try:
        spells.cast(wroot, g, "pc-mira", "sacred_flame", "goblin-1",
                    roll_fn=fixed(10), rng=random.Random(1))
        raise AssertionError("should have raised no_los")
    except EngineError as e:
        assert e.code == "no_los"
    try:
        spells.cast(wroot, g, "pc-mira", "flame_wave", None,
                    roll_fn=fixed(10), rng=random.Random(1), at=(9, 4))
        raise AssertionError("should have raised no_los")
    except EngineError as e:
        assert e.code == "no_los"
    sheet = worldfs.read_yaml(wroot / "state" / "party" / "pc-mira.yaml")
    assert sheet["spell_slots"][2]["current"] == 1                   # slot not spent


# ---------------------------------------------------------------------------
# Poisoned / frightened
# ---------------------------------------------------------------------------

def test_poisoned_attacker_rolls_and_checks_at_disadvantage(wroot):
    setup_fight(wroot)
    combat.set_effect(wroot, "pc-borin", "poisoned", -1)
    fn, calls = spy()
    r = combat.attack(wroot, "pc-borin", "goblin-1", attack_name="longsword",
                      adv=False, dis=False, roll_fn=fn, rng=random.Random(1))
    assert calls[-1] == (False, True)
    assert "attacker_poisoned" in r["dis_from"]
    res = runner.invoke(app, ["check", "--actor", "pc-borin", "--attr", "STR", "--dc", "10"])
    assert res.exit_code == 0, res.stdout
    assert json.loads(res.stdout)["dis_from"] == ["poisoned"]


def test_poisoned_contestant_rolls_at_disadvantage(wroot):
    setup_fight(wroot)
    combat.set_effect(wroot, "pc-borin", "poisoned", -1)
    fn, calls = spy()
    r = combat.grapple(wroot, "pc-borin", "goblin-1", roll_fn=fn)
    assert calls[-2] == (False, True)                                # attacker's roll
    assert calls[-1] == (False, False)                               # defender's roll
    assert r["contest"]["attacker"]["dis_from"] == ["poisoned"]


def test_frightened_without_source_always_applies(wroot):
    make_pc()
    combat.set_effect(wroot, "pc-borin", "frightened", -1)
    res = runner.invoke(app, ["check", "--actor", "pc-borin", "--attr", "WIS", "--dc", "10"])
    assert json.loads(res.stdout)["dis_from"] == ["frightened"]


def test_frightened_source_gated_by_line_of_sight_and_life(wroot):
    setup_fight(wroot)                                               # skirmish, wall at x=4 rows 0-2
    res = runner.invoke(app, ["effect", "add", "--target", "pc-borin",
                              "--name", "frightened", "--source", "goblin-1"])
    assert res.exit_code == 0, res.stdout
    fn, calls = spy()
    r = combat.attack(wroot, "pc-borin", "goblin-2", attack_name="longsword",
                      adv=False, dis=False, roll_fn=fn, rng=random.Random(1))
    assert "attacker_frightened" in r["dis_from"]                    # goblin-1 in plain view

    put_pos(wroot, "pc-borin", (3, 1))                               # wall breaks sight of goblin-1
    res = runner.invoke(app, ["check", "--actor", "pc-borin", "--attr", "STR", "--dc", "10"])
    assert "dis_from" not in json.loads(res.stdout)

    put_pos(wroot, "pc-borin", (10, 3))                              # back in view...
    combat.apply_damage(wroot, "goblin-1", 20, "test", rng=random.Random(1))
    res = runner.invoke(app, ["check", "--actor", "pc-borin", "--attr", "STR", "--dc", "10"])
    assert "dis_from" not in json.loads(res.stdout)                  # ...but the source is dead


def test_frightened_cannot_approach_the_source(wroot):
    setup_fight(wroot)
    combat.set_effect(wroot, "pc-borin", "frightened", -1, source="goblin-1")
    put_pos(wroot, "pc-borin", (5, 4))                               # goblin-1 is at [9,4]
    res = runner.invoke(app, ["move", "--actor", "pc-borin", "--to", "7,4"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "frightened"
    res = runner.invoke(app, ["move", "--actor", "pc-borin", "--to", "3,4"])
    assert res.exit_code == 0, res.stdout                            # fleeing is fine


# ---------------------------------------------------------------------------
# Light and darkness
# ---------------------------------------------------------------------------

def test_darkness_attack_modifiers_and_torchlight(wroot):
    make_pc()
    start_hideout(wroot)                                             # dark cells at [8..10,6]
    put_pos(wroot, "pc-borin", (9, 6))                               # in the dark
    put_pos(wroot, "goblin-1", (9, 5))                               # lit, adjacent
    fn, calls = spy()
    r = combat.attack(wroot, "goblin-1", "pc-borin", attack_name=None,
                      adv=False, dis=False, roll_fn=fn, rng=random.Random(1))
    assert "target_in_darkness" in r["dis_from"]
    r = combat.attack(wroot, "pc-borin", "goblin-1", attack_name="longsword",
                      adv=False, dis=False, roll_fn=fn, rng=random.Random(1))
    assert "attacker_in_darkness" in r["adv_from"]                   # unseen attacker

    runner.invoke(app, ["item", "add", "--actor", "pc-borin", "--item", "torch"])
    res = runner.invoke(app, ["equip", "--actor", "pc-borin", "--item", "torch"])
    assert res.exit_code == 0, res.stdout                            # torch grants `lit`
    r = combat.attack(wroot, "goblin-1", "pc-borin", attack_name=None,
                      adv=False, dis=False, roll_fn=fn, rng=random.Random(1))
    assert "dis_from" not in r                                       # torchlight gives him away


def test_hide_in_darkness_needs_no_cover_unless_lit(wroot):
    make_pc(**ROGUE)
    start_hideout(wroot)
    g = worldfs.load_game_for(wroot)
    put_pos(wroot, "pc-sly", (10, 6))                                # dark, in goblin sight lines
    r = combat.hide(wroot, g, "pc-sly", roll_fn=fixed(15))
    assert r["hidden"] is True and r["in_darkness"] is True

    runner.invoke(app, ["item", "add", "--actor", "pc-sly", "--item", "torch"])
    runner.invoke(app, ["equip", "--actor", "pc-sly", "--item", "torch"])
    try:
        combat.hide(wroot, g, "pc-sly", roll_fn=fixed(15))
        raise AssertionError("a lit torch is not stealthy")
    except EngineError as e:
        assert e.code == "seen"


def test_movers_cannot_spot_into_darkness(wroot):
    make_pc(**ROGUE)
    start_hideout(wroot)
    put_pos(wroot, "pc-sly", (10, 6))
    combat.hide(wroot, worldfs.load_game_for(wroot), "pc-sly", roll_fn=fixed(1))  # stealth 5
    res = runner.invoke(app, ["move", "--actor", "goblin-1", "--to", "9,5"])
    assert res.exit_code == 0, res.stdout
    assert "spotted" not in json.loads(res.stdout)                   # adjacent, but it's pitch dark
    assert "hidden" in effects_of(wroot, None, "pc-sly")


# ---------------------------------------------------------------------------
# Grapple / shove
# ---------------------------------------------------------------------------

def test_grapple_pins_escape_frees(wroot):
    setup_fight(wroot)                                               # borin adjacent to goblins
    r = combat.grapple(wroot, "goblin-1", "pc-borin", roll_fn=seq(20, 1))
    assert r["grappled"] is True
    assert get_enc(wroot)["grapples"] == {"pc-borin": "goblin-1"}
    res = runner.invoke(app, ["move", "--actor", "pc-borin", "--to", "10,1"])
    assert json.loads(res.stdout)["error"]["code"] == "held"

    r = combat.escape(wroot, "pc-borin", roll_fn=seq(1, 20))         # attacker roll 1 loses
    assert r["escaped"] is False
    r = combat.escape(wroot, "pc-borin", roll_fn=seq(20, 1))
    assert r["escaped"] is True
    assert "grappled" not in effects_of(wroot, None, "pc-borin")
    res = runner.invoke(app, ["move", "--actor", "pc-borin", "--to", "10,1"])
    assert res.exit_code == 0, res.stdout


def test_grapple_ties_go_to_defender_and_needs_adjacency(wroot):
    setup_fight(wroot)
    r = combat.grapple(wroot, "goblin-1", "pc-borin", roll_fn=seq(10, 10))
    assert r["grappled"] is False                                    # tie -> defender wins
    put_pos(wroot, "pc-borin", (4, 3))
    try:
        combat.grapple(wroot, "goblin-1", "pc-borin", roll_fn=seq(20, 1))
        raise AssertionError("should have raised out_of_range")
    except EngineError as e:
        assert e.code == "out_of_range"


def test_grapple_breaks_when_grappler_moves_away(wroot):
    setup_fight(wroot)
    combat.grapple(wroot, "goblin-1", "pc-borin", roll_fn=seq(20, 1))
    res = runner.invoke(app, ["move", "--actor", "goblin-1", "--to", "6,4"])
    assert res.exit_code == 0, res.stdout
    assert json.loads(res.stdout)["grapple_broken"] == ["goblin-1", "pc-borin"]
    assert "grappled" not in effects_of(wroot, None, "pc-borin")
    assert get_enc(wroot)["grapples"] == {}


def test_grappler_dropping_releases_hold(wroot):
    setup_fight(wroot)
    combat.grapple(wroot, "goblin-1", "pc-borin", roll_fn=seq(20, 1))
    r = combat.apply_damage(wroot, "goblin-1", 20, "test", rng=random.Random(1))
    assert r["dropped"] is True
    assert r["grapples_released"] == ["pc-borin"]
    assert "grappled" not in effects_of(wroot, None, "pc-borin")


def test_grapple_release_flag(wroot):
    setup_fight(wroot)
    combat.grapple(wroot, "goblin-1", "pc-borin", roll_fn=seq(20, 1))
    res = runner.invoke(app, ["grapple", "--actor", "goblin-1",
                              "--target", "pc-borin", "--release"])
    assert res.exit_code == 0, res.stdout
    assert json.loads(res.stdout)["released"] is True
    assert "grappled" not in effects_of(wroot, None, "pc-borin")


def test_grappled_flyer_cannot_ascend(wroot):
    make_pc()
    res = runner.invoke(app, ["--seed", "5", "encounter", "start",
                              "maps/encounters/skyfight.yaml"])
    assert res.exit_code == 0, res.stdout
    put_pos(wroot, "pc-borin", (6, 4))                               # adjacent to the bat
    combat.grapple(wroot, "pc-borin", "giant_bat-1", roll_fn=seq(20, 1))
    try:
        combat.ascend(wroot, "giant_bat-1")
        raise AssertionError("should have raised held")
    except EngineError as e:
        assert e.code == "held"


def test_grappling_from_hiding_reveals(wroot):
    make_pc(**ROGUE)
    start_hideout(wroot)
    put_pos(wroot, "pc-sly", (10, 6))                                # dark corner
    combat.hide(wroot, worldfs.load_game_for(wroot), "pc-sly", roll_fn=fixed(15))
    put_pos(wroot, "goblin-1", (9, 5))                               # wanders adjacent, sees nothing
    r = combat.grapple(wroot, "pc-sly", "goblin-1", roll_fn=seq(20, 1))
    assert r["grappled"] is True and r["revealed"] is True
    assert "hidden" not in effects_of(wroot, None, "pc-sly")


def test_shove_knocks_prone(wroot):
    setup_fight(wroot)
    r = combat.shove(wroot, "pc-borin", "goblin-1", roll_fn=seq(20, 1))
    assert r["prone"] is True
    assert "prone" in effects_of(wroot, None, "goblin-1")
    r = combat.shove(wroot, "pc-borin", "goblin-2", roll_fn=seq(1, 20))
    assert r["prone"] is False
    assert "prone" not in effects_of(wroot, None, "goblin-2")


# ---------------------------------------------------------------------------
# Sneak attack
# ---------------------------------------------------------------------------

def _rogue_fight(wroot):
    """Rogue and fighter both adjacent to goblin-1 at [9,4]."""
    make_pc(**ROGUE)
    make_pc()                                                        # pc-borin the ally
    res = runner.invoke(app, ["--seed", "5", "encounter", "start",
                              "maps/encounters/skirmish.yaml", "--pcs", "pc-sly,pc-borin"])
    assert res.exit_code == 0, res.stdout
    put_pos(wroot, "pc-sly", (8, 4))
    put_pos(wroot, "pc-borin", (10, 3))


def test_sneak_attack_with_adjacent_ally_once_per_round(wroot):
    _rogue_fight(wroot)
    fn, calls = spy()
    r = combat.attack(wroot, "pc-sly", "goblin-1", attack_name="dagger",
                      adv=False, dis=False, roll_fn=fn, rng=random.Random(1))
    assert calls[-1] == (False, False)                               # no adv needed, just the ally
    assert 1 <= r["sneak_attack"] <= 6
    r2 = combat.attack(wroot, "pc-sly", "goblin-1", attack_name="dagger",
                       adv=False, dis=False, roll_fn=fn, rng=random.Random(2))
    assert "sneak_attack" not in r2                                  # once per round

    for _ in range(len(get_enc(wroot)["order"])):                    # advance to next round
        res = runner.invoke(app, ["encounter", "next"])
        assert res.exit_code == 0, res.stdout
    r3 = combat.attack(wroot, "pc-sly", "goblin-1", attack_name="dagger",
                       adv=False, dis=False, roll_fn=fn, rng=random.Random(3))
    assert "sneak_attack" in r3


def test_no_sneak_attack_without_ally_or_advantage(wroot):
    _rogue_fight(wroot)
    put_pos(wroot, "pc-borin", (2, 3))                               # ally out of position
    r = combat.attack(wroot, "pc-sly", "goblin-1", attack_name="dagger",
                      adv=False, dis=False, roll_fn=fixed(15), rng=random.Random(1))
    assert "sneak_attack" not in r
    r = combat.attack(wroot, "pc-sly", "goblin-1", attack_name="dagger",
                      adv=True, dis=False, roll_fn=fixed(15), rng=random.Random(1))
    assert "sneak_attack" in r                                       # advantage alone qualifies


def test_disadvantage_denies_sneak_attack(wroot):
    _rogue_fight(wroot)
    combat.set_effect(wroot, "pc-sly", "prone", -1)                  # attacker prone -> dis
    r = combat.attack(wroot, "pc-sly", "goblin-1", attack_name="dagger",
                      adv=False, dis=False, roll_fn=fixed(15), rng=random.Random(1))
    assert "sneak_attack" not in r


def test_sneak_attack_dice_scale_with_level(wroot):
    make_pc(**ROGUE)
    runner.invoke(app, ["xp", "grant", "--amount", "9999", "--reason", "test"])
    runner.invoke(app, ["--seed", "1", "level", "up", "--actor", "pc-sly"])
    res = runner.invoke(app, ["--seed", "1", "level", "up", "--actor", "pc-sly"])
    assert res.exit_code == 0, res.stdout
    make_pc()
    res = runner.invoke(app, ["--seed", "5", "encounter", "start",
                              "maps/encounters/skirmish.yaml", "--pcs", "pc-sly,pc-borin"])
    assert res.exit_code == 0, res.stdout
    put_pos(wroot, "pc-sly", (8, 4))
    put_pos(wroot, "pc-borin", (10, 3))
    r = combat.attack(wroot, "pc-sly", "goblin-1", attack_name="dagger",
                      adv=False, dis=False, roll_fn=fixed(15), rng=random.Random(1))
    assert 2 <= r["sneak_attack"] <= 12                              # level 3 -> 2d6


# ---------------------------------------------------------------------------
# Falling
# ---------------------------------------------------------------------------

def test_fall_command_damages_and_flattens(wroot):
    make_pc()
    res = runner.invoke(app, ["--seed", "5", "encounter", "start",
                              "maps/encounters/skyfight.yaml"])
    assert res.exit_code == 0, res.stdout
    combat.ascend(wroot, "giant_bat-1")
    r = combat.fall(wroot, "giant_bat-1", random.Random(1))
    assert 2 <= r["damage"] <= 12
    assert get_enc(wroot)["aloft"]["giant_bat-1"] is False
    assert "prone" in effects_of(wroot, None, "giant_bat-1")
    try:
        combat.fall(wroot, "giant_bat-1", random.Random(1))
        raise AssertionError("should have raised not_aloft")
    except EngineError as e:
        assert e.code == "not_aloft"


def test_removing_flying_effect_mid_air_causes_fall(wroot):
    setup_fight(wroot)
    combat.set_effect(wroot, "pc-borin", "flying", -1)
    runner.invoke(app, ["ascend", "--actor", "pc-borin"])
    res = runner.invoke(app, ["effect", "remove", "--target", "pc-borin", "--name", "flying"])
    assert res.exit_code == 0, res.stdout
    data = json.loads(res.stdout)
    assert data["fell"]["damage"] >= 2
    assert get_enc(wroot)["aloft"]["pc-borin"] is False
    assert "prone" in effects_of(wroot, None, "pc-borin")


def test_flying_effect_expiry_causes_fall(wroot):
    setup_fight(wroot)
    combat.set_effect(wroot, "pc-borin", "flying", 1)
    runner.invoke(app, ["ascend", "--actor", "pc-borin"])
    fell = None
    for _ in range(len(get_enc(wroot)["order"])):
        res = runner.invoke(app, ["encounter", "next"])
        assert res.exit_code == 0, res.stdout
        data = json.loads(res.stdout)
        if "fell" in data:
            fell = data["fell"]
    assert fell and fell[0]["actor"] == "pc-borin"
    assert get_enc(wroot)["aloft"]["pc-borin"] is False


def test_dropping_to_zero_while_aloft_falls(wroot):
    make_pc()
    res = runner.invoke(app, ["--seed", "5", "encounter", "start",
                              "maps/encounters/skyfight.yaml"])
    assert res.exit_code == 0, res.stdout
    combat.ascend(wroot, "giant_bat-1")
    r = combat.apply_damage(wroot, "giant_bat-1", 10, "test", rng=random.Random(1))
    assert r["dropped"] is True and r["fell"] >= 2
    enc = get_enc(wroot)
    assert enc["aloft"]["giant_bat-1"] is False
    assert "prone" in combat.effect_names(enc["monsters"]["giant_bat-1"])
