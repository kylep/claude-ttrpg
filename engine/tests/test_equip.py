import json
import shutil
from pathlib import Path

from typer.testing import CliRunner

from ttrpg_engine import chargen, combat, derive, game, worldfs
from ttrpg_engine.cli import app
from conftest import make_pc, FIXTURE_GAME

runner = CliRunner()


def _sheet(wroot, pc):
    return worldfs.read_yaml(wroot / "state" / "party" / f"{pc}.yaml")


def test_starting_gear_marked_equipped(wroot):
    pc = make_pc()
    lines = {l["item"]: l for l in _sheet(wroot, pc)["inventory"]}
    assert lines["chain_mail"]["equipped"] is True
    assert lines["longsword"]["equipped"] is True


def test_derive_recompute_matches_chargen_values(wroot):
    pc = make_pc()
    g = game.load(FIXTURE_GAME)
    sheet = _sheet(wroot, pc)
    ac_before, attacks_before = sheet["ac"], sheet["attacks"]
    derive.recompute(sheet, g)
    assert sheet["ac"] == ac_before == 16
    assert sheet["attacks"] == attacks_before
    assert sheet["attacks"][0] == {"name": "longsword", "attack_mod": 4,
                                    "damage": "1d8+2", "range": 1}


def test_equip_requires_carried_item(wroot):
    pc = make_pc()
    res = runner.invoke(app, ["equip", "--actor", pc, "--item", "dagger"])
    assert json.loads(res.stdout)["error"]["code"] == "not_carried"


def test_equip_fine_longsword_adds_bonus_attack(wroot):
    pc = make_pc()
    runner.invoke(app, ["item", "add", "--actor", pc, "--item", "fine_longsword"])
    res = runner.invoke(app, ["equip", "--actor", pc, "--item", "fine_longsword"])
    assert res.exit_code == 0, res.stdout
    sheet = _sheet(wroot, pc)
    by_name = {a["name"]: a for a in sheet["attacks"]}
    assert by_name["fine_longsword"] == {"name": "fine_longsword", "attack_mod": 5,
                                          "damage": "1d8+3", "range": 1}
    assert by_name["longsword"]["attack_mod"] == 4


def test_loot_and_equip_armor_changes_ac(wroot):
    pc = make_pc()
    runner.invoke(app, ["unequip", "--actor", pc, "--item", "chain_mail"])
    runner.invoke(app, ["item", "add", "--actor", pc, "--item", "leather_armor"])
    res = runner.invoke(app, ["equip", "--actor", pc, "--item", "leather_armor"])
    assert res.exit_code == 0, res.stdout
    assert _sheet(wroot, pc)["ac"] == 12  # ac_base 11 + DEX mod 1 (DEX 13)


def test_second_armor_conflict(wroot):
    pc = make_pc()
    runner.invoke(app, ["item", "add", "--actor", pc, "--item", "leather_armor"])
    res = runner.invoke(app, ["equip", "--actor", pc, "--item", "leather_armor"])
    assert json.loads(res.stdout)["error"]["code"] == "armor_conflict"


def test_ward_ring_equip_and_unequip_effect(wroot):
    pc = make_pc()
    runner.invoke(app, ["item", "add", "--actor", pc, "--item", "ward_ring"])
    res = runner.invoke(app, ["equip", "--actor", pc, "--item", "ward_ring"])
    assert res.exit_code == 0, res.stdout
    assert {"name": "blessed", "duration": -1} in _sheet(wroot, pc)["effects"]
    res = runner.invoke(app, ["unequip", "--actor", pc, "--item", "ward_ring"])
    assert res.exit_code == 0, res.stdout
    assert {"name": "blessed", "duration": -1} not in _sheet(wroot, pc)["effects"]


def test_two_blessed_granters_unequip_one_keeps_effect(wroot):
    pc = make_pc()
    runner.invoke(app, ["item", "add", "--actor", pc, "--item", "ward_ring"])
    runner.invoke(app, ["item", "add", "--actor", pc, "--item", "lucky_charm"])
    runner.invoke(app, ["equip", "--actor", pc, "--item", "ward_ring"])
    runner.invoke(app, ["equip", "--actor", pc, "--item", "lucky_charm"])
    res = runner.invoke(app, ["unequip", "--actor", pc, "--item", "ward_ring"])
    assert res.exit_code == 0, res.stdout
    assert {"name": "blessed", "duration": -1} in _sheet(wroot, pc)["effects"]


def test_grim_helm_curse_lifecycle(wroot):
    pc = make_pc()
    runner.invoke(app, ["unequip", "--actor", pc, "--item", "chain_mail"])
    runner.invoke(app, ["item", "add", "--actor", pc, "--item", "grim_helm"])
    res = runner.invoke(app, ["equip", "--actor", pc, "--item", "grim_helm"])
    assert res.exit_code == 0, res.stdout
    payload = json.loads(res.stdout)
    assert payload["cursed"] is True
    sheet = _sheet(wroot, pc)
    assert {"name": "poisoned", "duration": -1} in sheet["effects"]
    assert sheet["ac"] == 17  # ac_base 16 + bonus 1, no dex

    res = runner.invoke(app, ["unequip", "--actor", pc, "--item", "grim_helm"])
    assert json.loads(res.stdout)["error"]["code"] == "cursed"

    res = runner.invoke(app, ["item", "dispel", "--actor", pc, "--item", "grim_helm"])
    assert res.exit_code == 0, res.stdout
    sheet = _sheet(wroot, pc)
    assert not any(e["name"] == "poisoned" for e in sheet["effects"])
    assert sheet["ac"] == 17  # bonus keeps applying while dispelled+equipped

    res = runner.invoke(app, ["unequip", "--actor", pc, "--item", "grim_helm"])
    assert res.exit_code == 0, res.stdout
    sheet = _sheet(wroot, pc)
    assert sheet["ac"] == 10 + chargen.attr_mod(13)  # unarmored, DEX 13


def test_long_rest_keeps_equipment_effects_clears_others(wroot):
    pc = make_pc()
    runner.invoke(app, ["item", "add", "--actor", pc, "--item", "ward_ring"])
    runner.invoke(app, ["equip", "--actor", pc, "--item", "ward_ring"])
    combat.set_effect(wroot, pc, "poisoned", -1)
    res = runner.invoke(app, ["rest", "--type", "long"])
    assert res.exit_code == 0, res.stdout
    names = {e["name"] for e in _sheet(wroot, pc)["effects"]}
    assert names == {"blessed"}


def test_remove_equipped_item_blocked(wroot):
    pc = make_pc()
    res = runner.invoke(app, ["item", "remove", "--actor", pc, "--item", "chain_mail"])
    assert json.loads(res.stdout)["error"]["code"] == "equipped"


def test_validate_catches_unknown_grants_effect(tmp_path):
    broken = tmp_path / "broken"
    shutil.copytree(FIXTURE_GAME, broken)
    items_path = broken / "ruleset" / "items.yaml"
    items_path.write_text(items_path.read_text() +
                          "\ncursed_bauble: {type: gear, price: 1, "
                          "grants_effect: {name: nonexistent_effect}}\n")
    errors = game.validate(broken)
    assert any("cursed_bauble: unknown effect nonexistent_effect" in e for e in errors)


def test_unequip_removes_flag_entirely(wroot):
    pc = make_pc()
    runner.invoke(app, ["item", "add", "--actor", pc, "--item", "ward_ring"])
    runner.invoke(app, ["equip", "--actor", pc, "--item", "ward_ring"])
    res = runner.invoke(app, ["unequip", "--actor", pc, "--item", "ward_ring"])
    assert res.exit_code == 0, res.stdout
    line = next(l for l in _sheet(wroot, pc)["inventory"] if l["item"] == "ward_ring")
    assert "equipped" not in line
