import json

from typer.testing import CliRunner

from ttrpg_engine import combat, worldfs
from ttrpg_engine.cli import app
from conftest import make_pc

runner = CliRunner()


def fixed(nat):
    return lambda mod, adv, dis: (nat, nat + mod)


def setup_fight(wroot):
    make_pc()
    res = runner.invoke(app, ["--seed", "5", "encounter", "start",
                              "maps/encounters/skirmish.yaml"])
    assert res.exit_code == 0, res.stdout
    # put attacker adjacent to both goblins so range checks pass
    enc = worldfs.read_yaml(wroot / "state" / "encounter.yaml")
    enc["positions"]["pc-borin"] = [10, 3]
    worldfs.write_yaml(wroot / "state" / "encounter.yaml", enc)


def test_attack_hit_and_crit(wroot):
    import random
    setup_fight(wroot)
    rng = random.Random(1)
    r = combat.attack(wroot, "pc-borin", "goblin-1", attack_name=None,
                      adv=False, dis=False, roll_fn=fixed(15), rng=rng)
    assert r["hit"] is True and r["damage"] >= 3       # 1d8+2
    enc = worldfs.read_yaml(wroot / "state" / "encounter.yaml")
    assert enc["monsters"]["goblin-1"]["hp"] == 7 - r["damage"] or enc["monsters"]["goblin-1"]["dead"]
    r2 = combat.attack(wroot, "pc-borin", "goblin-2", attack_name=None,
                       adv=False, dis=False, roll_fn=fixed(20), rng=rng)
    assert r2["crit"] == "hit" and r2["damage"] >= 4   # two damage dice + mod


def test_resolve_hit_rules():
    assert combat.resolve_hit(20, 5, 99) == (True, "hit")    # nat 20 always hits + crits
    assert combat.resolve_hit(1, 99, 5) == (False, "fumble")  # nat 1 always misses
    assert combat.resolve_hit(10, 15, 14) == (True, None)     # meets AC
    assert combat.resolve_hit(10, 13, 14) == (False, None)    # under AC


def test_roll_damage_doubles_dice_on_crit():
    import random
    seed = 7
    normal = combat.roll_damage("2d6", random.Random(seed), None)
    crit = combat.roll_damage("2d6", random.Random(seed), "hit")
    # crit re-rolls the dice: same first roll, plus a second dice-only roll
    base = dice_total("2d6", seed)
    extra = second_roll_total("2d6", seed)
    assert normal == base
    assert crit == base + extra
    assert crit > normal


def dice_total(expr, seed):
    import random
    from ttrpg_engine import dice
    return dice.roll(expr, random.Random(seed)).total


def second_roll_total(expr, seed):
    import random
    from ttrpg_engine import dice
    rng = random.Random(seed)
    dice.roll(expr, rng)                      # burn the first roll
    return sum(dice.roll(expr, rng).rolls)    # dice of the second roll


def test_nat1_misses_even_vs_ac0(wroot):
    import random
    setup_fight(wroot)
    enc = worldfs.read_yaml(wroot / "state" / "encounter.yaml")
    enc["monsters"]["goblin-1"]["ac"] = 0
    worldfs.write_yaml(wroot / "state" / "encounter.yaml", enc)
    r = combat.attack(wroot, "pc-borin", "goblin-1", attack_name=None,
                      adv=False, dis=False, roll_fn=fixed(1), rng=random.Random(1))
    assert r["hit"] is False and r["damage"] == 0


def test_monster_death_emits_timeline_event(wroot):
    setup_fight(wroot)
    combat.apply_damage(wroot, "goblin-1", 99, source="test")
    events = [worldfs.read_yaml(p) for p in sorted((wroot / "timeline").glob("*.yaml"))]
    deaths = [e for e in events if e.get("type") == "death"]
    assert any("goblin-1" in e["actors"] for e in deaths)   # monsters get a death event too


def test_out_of_range_fails(wroot):
    setup_fight(wroot)
    # Move PC far from goblin-2 to test out of range
    enc = worldfs.read_yaml(wroot / "state" / "encounter.yaml")
    enc["positions"]["pc-borin"] = [0, 0]
    worldfs.write_yaml(wroot / "state" / "encounter.yaml", enc)
    res = runner.invoke(app, ["attack", "--attacker", "goblin-2", "--target", "pc-borin"])
    assert res.exit_code == 1                           # goblin-2 at [10,4], pc at [0,0], range 1
    assert json.loads(res.stdout)["error"]["code"] == "out_of_range"


def test_pc_drops_to_dying_then_death_saves(wroot):
    setup_fight(wroot)
    combat.apply_damage(wroot, "pc-borin", 99, source="test")
    sheet = worldfs.read_yaml(wroot / "state" / "party" / "pc-borin.yaml")
    assert sheet["hp"] == 0
    names = {e["name"] for e in sheet["effects"]}
    assert {"unconscious", "dying"} <= names
    r = combat.death_save(wroot, "pc-borin", roll_fn=fixed(20))
    sheet = worldfs.read_yaml(wroot / "state" / "party" / "pc-borin.yaml")
    assert r["result"] == "revived" and sheet["hp"] == 1 and sheet["effects"] == []
    combat.apply_damage(wroot, "pc-borin", 99, source="test")
    for _ in range(3):
        r = combat.death_save(wroot, "pc-borin", roll_fn=fixed(2))
    assert r["result"] == "dead"
    sheet = worldfs.read_yaml(wroot / "state" / "party" / "pc-borin.yaml")
    assert "dead" in {e["name"] for e in sheet["effects"]}


def test_heal_clears_dying(wroot):
    setup_fight(wroot)
    combat.apply_damage(wroot, "pc-borin", 99, source="test")
    combat.apply_heal(wroot, "pc-borin", 5, source="potion")
    sheet = worldfs.read_yaml(wroot / "state" / "party" / "pc-borin.yaml")
    assert sheet["hp"] == 5 and sheet["effects"] == []
