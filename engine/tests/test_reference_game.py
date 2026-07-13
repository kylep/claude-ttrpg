import json
import random
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ttrpg_engine import combat, game, worldfs
from ttrpg_engine.cli import app
from ttrpg_engine.errors import EngineError
from test_attack import fixed
from test_tactics import seq, spy

REFERENCE = Path(__file__).resolve().parents[2] / "games" / "reference"

runner = CliRunner()


def test_reference_game_validates():
    assert REFERENCE.exists(), "games/reference missing"
    assert game.validate(REFERENCE) == []


def test_reference_has_four_classes_and_races():
    g = game.load(REFERENCE)
    assert set(g["classes"]) == {"fighter", "rogue", "cleric", "wizard"}
    assert set(g["races"]) == {"human", "elf", "dwarf", "halfling"}
    for cls in g["classes"].values():
        assert set(cls["levels"]) == {1, 2, 3, 4, 5}


# ---------------------------------------------------------------------------
# Campaign smoke tests: the tactics kit run on the shipped encounters
# ---------------------------------------------------------------------------

@pytest.fixture
def ref_root(tmp_path, monkeypatch):
    root = tmp_path / "refworld"
    worldfs.init_world(root, REFERENCE, "Reference World")
    monkeypatch.chdir(root)
    return root


def _make(name, cls, race, assign, skills):
    res = runner.invoke(app, ["char", "create", "--name", name, "--class", cls,
                              "--race", race, "--assign", assign, "--skills", skills])
    assert res.exit_code == 0, res.stdout
    return f"pc-{name.lower()}"


def test_latch_vault_rewards_the_stealth_kit(ref_root):
    """Beat 13 as written: enter seen, slip behind the shelving, hide, sneak
    up on the Latchwight, ambush it with engine-applied sneak attack."""
    _make("Nim", "rogue", "elf", "DEX=15,STR=14,CON=13,WIS=12,INT=10,CHA=8",
          "stealth,acrobatics,perception")
    res = runner.invoke(app, ["--seed", "7", "encounter", "start",
                              "maps/encounters/ward-rogue.yaml", "--pcs", "pc-nim"])
    assert res.exit_code == 0, res.stdout

    # the ward watches the door: hiding at the spawn fails
    try:
        combat.hide(ref_root, worldfs.load_game_for(ref_root), "pc-nim", roll_fn=fixed(15))
        raise AssertionError("spawn is in the Latchwight's sight")
    except EngineError as e:
        assert e.code == "seen"

    # two squares into the shelving's shadow, then hide
    res = runner.invoke(app, ["move", "--actor", "pc-nim", "--to", "3,1"])
    assert res.exit_code == 0, res.stdout
    r = combat.hide(ref_root, worldfs.load_game_for(ref_root), "pc-nim", roll_fn=fixed(15))
    assert r["hidden"] and r["stealth"] >= 15

    # sneak to arm's reach: stealth beats the ward's passive perception
    res = runner.invoke(app, ["move", "--actor", "pc-nim", "--to", "7,2"])
    assert res.exit_code == 0, res.stdout
    assert "revealed_by" not in json.loads(res.stdout)

    fn, calls = spy()
    r = combat.attack(ref_root, "pc-nim", "latchwight-1", attack_name="dagger",
                      adv=False, dis=False, roll_fn=fn, rng=random.Random(3))
    assert calls[-1] == (True, False)                    # ambush advantage
    assert r["revealed"] is True
    assert 1 <= r["sneak_attack"] <= 6

    # the shelving gambit: a real contested shove, then melee at advantage
    r = combat.shove(ref_root, "pc-nim", "latchwight-1", roll_fn=seq(20, 1))
    assert r["prone"] is True
    r = combat.attack(ref_root, "pc-nim", "latchwight-1", attack_name="dagger",
                      adv=False, dis=False, roll_fn=fn, rng=random.Random(4))
    assert "target_prone" in r["adv_from"]


def test_lych_gate_flying_fight(ref_root):
    """The Lych-Crake per its bestiary notes: unreachable aloft, grappled
    flat-footed on the ground, and shot down for an automatic fall."""
    _make("Bron", "fighter", "human", "STR=15,CON=14,DEX=13,WIS=12,INT=10,CHA=8",
          "athletics,perception")
    res = runner.invoke(app, ["--seed", "7", "encounter", "start",
                              "maps/encounters/lych-gate.yaml"])
    assert res.exit_code == 0, res.stdout

    # the gate wall screens the approach: even the fighter can hide here
    r = combat.hide(ref_root, worldfs.load_game_for(ref_root), "pc-bron", roll_fn=fixed(10))
    assert r["hidden"] is True

    combat.ascend(ref_root, "lych_crake-1")
    enc = worldfs.read_yaml(ref_root / "state" / "encounter.yaml")
    enc["positions"]["pc-bron"] = [6, 3]                 # adjacent to the aloft crake
    worldfs.write_yaml(ref_root / "state" / "encounter.yaml", enc)

    try:
        combat.attack(ref_root, "pc-bron", "lych_crake-1", attack_name="longsword",
                      adv=False, dis=False, roll_fn=fixed(15), rng=random.Random(1))
        raise AssertionError("melee should not reach an aloft crake")
    except EngineError as e:
        assert e.code == "unreachable"
    try:
        combat.grapple(ref_root, "pc-bron", "lych_crake-1", roll_fn=seq(20, 1))
        raise AssertionError("grapple should not reach an aloft crake")
    except EngineError as e:
        assert e.code == "unreachable"

    # it lands to peck; grab it so it cannot take off again
    combat.land(ref_root, "lych_crake-1")
    r = combat.grapple(ref_root, "pc-bron", "lych_crake-1", roll_fn=seq(20, 1))
    assert r["grappled"] is True
    try:
        combat.ascend(ref_root, "lych_crake-1")
        raise AssertionError("a grappled crake cannot take off")
    except EngineError as e:
        assert e.code == "held"

    # or shoot it out of the sky: dropped aloft means an automatic fall
    combat.grapple(ref_root, "pc-bron", "lych_crake-1", roll_fn=None, release=True)
    combat.ascend(ref_root, "lych_crake-1")
    r = combat.apply_damage(ref_root, "lych_crake-1", 15, "arrow", rng=random.Random(1))
    assert r["dropped"] is True and r["fell"] >= 2
    enc = worldfs.read_yaml(ref_root / "state" / "encounter.yaml")
    assert enc["aloft"]["lych_crake-1"] is False
    assert "prone" in combat.effect_names(enc["monsters"]["lych_crake-1"])
