import json

from typer.testing import CliRunner

from ttrpg_engine import worldfs
from ttrpg_engine.cli import app
from conftest import make_pc

runner = CliRunner()


def start(seed="5"):
    make_pc()
    res = runner.invoke(app, ["--seed", seed, "encounter", "start",
                              "maps/encounters/skirmish.yaml"])
    assert res.exit_code == 0, res.stdout
    return json.loads(res.stdout)


def test_start_seats_and_orders(wroot):
    data = start()
    enc = worldfs.read_yaml(wroot / "state" / "encounter.yaml")
    assert set(enc["order"]) == {"pc-borin", "goblin-1", "goblin-2"}
    assert enc["positions"]["pc-borin"] == [1, 3]          # first spawn
    assert enc["monsters"]["goblin-1"]["hp"] == 7
    assert data["order"] == enc["order"]
    assert enc["round"] == 1 and enc["turn"] == 0


def test_next_wraps_and_ticks_effects(wroot):
    start()
    enc = worldfs.read_yaml(wroot / "state" / "encounter.yaml")
    enc["monsters"]["goblin-1"]["effects"] = [{"name": "blessed", "duration": 1}]
    worldfs.write_yaml(wroot / "state" / "encounter.yaml", enc)
    for _ in range(3):                                     # 3 combatants -> full round
        res = runner.invoke(app, ["encounter", "next"])
    data = json.loads(res.stdout)
    assert data["round"] == 2 and data["expired_effects"] == [["goblin-1", "blessed"]]


def test_end_awards_xp_and_loot(wroot):
    start()
    res = runner.invoke(app, ["--seed", "2", "encounter", "end"])
    data = json.loads(res.stdout)
    assert data["xp_each"] == 100                          # 2 goblins * 50 / 1 PC
    sheet = worldfs.read_yaml(wroot / "state" / "party" / "pc-borin.yaml")
    assert sheet["xp"] == 100
    party = worldfs.read_yaml(wroot / "state" / "party.yaml")
    assert party["gold"] == data["gold"] > 0
    assert not (wroot / "state" / "encounter.yaml").exists()
