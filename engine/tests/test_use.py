import json
import random

from typer.testing import CliRunner

from ttrpg_engine import combat, game, inventory, worldfs
from ttrpg_engine.cli import app
from ttrpg_engine.errors import EngineError
from conftest import FIXTURE_GAME, make_pc
from test_attack import setup_fight

runner = CliRunner()


def _give(actor, item, qty=1):
    res = runner.invoke(app, ["item", "add", "--actor", actor, "--item", item,
                              "--qty", str(qty)])
    assert res.exit_code == 0, res.stdout


def _sheet(wroot, actor):
    return worldfs.read_yaml(wroot / "state" / "party" / f"{actor}.yaml")


def test_use_healing_potion_on_self(wroot):
    make_pc()
    _give("pc-borin", "healing_potion", 2)
    combat.apply_damage(wroot, "pc-borin", 5, "test")
    res = runner.invoke(app, ["--seed", "1", "item", "use", "--actor", "pc-borin",
                              "--item", "healing_potion"])
    assert res.exit_code == 0, res.stdout
    data = json.loads(res.stdout)
    assert data["target"] == "pc-borin" and data["qty_left"] == 1
    assert 4 <= data["healed"] <= 5                                  # 2d4+2, capped by 5 missing hp
    sheet = _sheet(wroot, "pc-borin")
    assert sheet["hp"] == sheet["max_hp"] - 5 + data["healed"]
    assert next(l for l in sheet["inventory"] if l["item"] == "healing_potion")["qty"] == 1


def test_last_potion_line_disappears(wroot):
    make_pc()
    _give("pc-borin", "healing_potion")
    combat.apply_damage(wroot, "pc-borin", 3, "test")
    r = inventory.use(wroot, worldfs.load_game_for(wroot), "pc-borin",
                      "healing_potion", None, random.Random(1))
    assert r["qty_left"] == 0
    assert all(l["item"] != "healing_potion" for l in _sheet(wroot, "pc-borin")["inventory"])
    try:
        inventory.use(wroot, worldfs.load_game_for(wroot), "pc-borin",
                      "healing_potion", None, random.Random(1))
        raise AssertionError("should have raised not_carried")
    except EngineError as e:
        assert e.code == "not_carried"


def test_potion_revives_a_dying_ally(wroot):
    make_pc()
    make_pc(name="Mira", cls="cleric", race="human",
            assign="WIS=15,CON=14,STR=13,DEX=12,INT=10,CHA=8", skills="insight,medicine")
    _give("pc-borin", "healing_potion")
    combat.apply_damage(wroot, "pc-mira", 99, "test")
    assert "dying" in combat.effect_names(_sheet(wroot, "pc-mira"))
    r = inventory.use(wroot, worldfs.load_game_for(wroot), "pc-borin",
                      "healing_potion", "pc-mira", random.Random(1))
    assert r["healed"] >= 4
    sheet = _sheet(wroot, "pc-mira")
    assert sheet["hp"] > 0
    assert combat.effect_names(sheet) == set()                       # unconscious/dying cleared


def test_use_in_combat_requires_adjacency_and_costs_the_gear_action(wroot):
    make_pc(name="Mira", cls="cleric", race="human",
            assign="WIS=15,CON=14,STR=13,DEX=12,INT=10,CHA=8", skills="insight,medicine")
    setup_fight(wroot)                        # seats both; moves pc-borin to [10,3], Mira at spawn
    _give("pc-borin", "healing_potion", 3)
    g = worldfs.load_game_for(wroot)
    try:
        inventory.use(wroot, g, "pc-borin", "healing_potion", "pc-mira", random.Random(1))
        raise AssertionError("pc-mira spawned across the map")
    except EngineError as e:
        assert e.code == "out_of_range"

    r = inventory.use(wroot, g, "pc-borin", "healing_potion", None, random.Random(1))
    assert r["qty_left"] == 2
    try:
        inventory.use(wroot, g, "pc-borin", "healing_potion", None, random.Random(1))
        raise AssertionError("second item use in one round")
    except EngineError as e:
        assert e.code == "action_spent"
    r = inventory.use(wroot, g, "pc-borin", "healing_potion", None, random.Random(1),
                      force=True)
    assert r["forced"] is True


def test_effect_and_damage_consumables(wroot):
    setup_fight(wroot)
    _give("pc-borin", "battle_tonic")
    _give("pc-borin", "fire_flask")
    g = worldfs.load_game_for(wroot)
    r = inventory.use(wroot, g, "pc-borin", "battle_tonic", None, random.Random(1))
    assert r["effect"] == {"name": "blessed", "duration": 3}
    assert {"name": "blessed", "duration": 3} in _sheet(wroot, "pc-borin")["effects"]

    r = inventory.use(wroot, g, "pc-borin", "fire_flask", "goblin-1", random.Random(1),
                      force=True)                                    # gear action already spent
    assert 2 <= r["damage"] <= 8
    enc = worldfs.read_yaml(wroot / "state" / "encounter.yaml")
    assert enc["monsters"]["goblin-1"]["hp"] <= 7 - r["damage"] + 7  # damaged or dead


def test_use_rejects_non_consumables_and_unknown_items(wroot):
    make_pc()
    g = worldfs.load_game_for(wroot)
    try:
        inventory.use(wroot, g, "pc-borin", "longsword", None, random.Random(1))
        raise AssertionError("should have raised not_consumable")
    except EngineError as e:
        assert e.code == "not_consumable"
    try:
        inventory.use(wroot, g, "pc-borin", "elixir_of_nothing", None, random.Random(1))
        raise AssertionError("should have raised unknown_item")
    except EngineError as e:
        assert e.code == "unknown_item"


def test_validate_rejects_inert_consumable(tmp_path):
    import shutil
    broken = tmp_path / "broken"
    shutil.copytree(FIXTURE_GAME, broken)
    items = broken / "ruleset" / "items.yaml"
    items.write_text(items.read_text() + "\nmystery_vial: {type: consumable, price: 5}\n")
    errors = game.validate(broken)
    assert any("mystery_vial" in e and "consumable" in e for e in errors)
