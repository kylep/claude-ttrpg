import json

from typer.testing import CliRunner

from ttrpg_engine import worldfs
from ttrpg_engine.cli import app
from conftest import make_pc

runner = CliRunner()


def test_item_add_merges_and_remove(wroot):
    pc = make_pc()
    runner.invoke(app, ["item", "add", "--actor", pc, "--item", "torch", "--qty", "2"])
    res = runner.invoke(app, ["item", "add", "--actor", pc, "--item", "torch", "--qty", "3"])
    assert res.exit_code == 0, res.stdout
    sheet = worldfs.read_yaml(wroot / "state" / "party" / f"{pc}.yaml")
    assert {"item": "torch", "qty": 5} in sheet["inventory"]
    res = runner.invoke(app, ["item", "remove", "--actor", pc, "--item", "torch", "--qty", "9"])
    assert json.loads(res.stdout)["error"]["code"] == "not_enough"


def test_unknown_item_rejected(wroot):
    pc = make_pc()
    res = runner.invoke(app, ["item", "add", "--actor", pc, "--item", "vorpal_sword"])
    assert json.loads(res.stdout)["error"]["code"] == "unknown_item"


def test_item_add_zero_qty_rejected(wroot):
    pc = make_pc()
    res = runner.invoke(app, ["item", "add", "--actor", pc, "--item", "torch", "--qty", "0"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "bad_qty"


def test_item_remove_zero_qty_rejected(wroot):
    pc = make_pc()
    runner.invoke(app, ["item", "add", "--actor", pc, "--item", "torch", "--qty", "2"])
    res = runner.invoke(app, ["item", "remove", "--actor", pc, "--item", "torch", "--qty", "0"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "bad_qty"


def test_gold_pc_and_party(wroot):
    pc = make_pc()
    runner.invoke(app, ["gold", "spend", "--amount", "4", "--actor", pc])
    sheet = worldfs.read_yaml(wroot / "state" / "party" / f"{pc}.yaml")
    assert sheet["gold"] == 6                      # fighter starts with gold 10
    res = runner.invoke(app, ["gold", "spend", "--amount", "999", "--party"])
    assert json.loads(res.stdout)["error"]["code"] == "not_enough"
    runner.invoke(app, ["gold", "add", "--amount", "50", "--party"])
    party = worldfs.read_yaml(wroot / "state" / "party.yaml")
    assert party["gold"] == 50


def test_gold_spend_negative_amount_rejected(wroot):
    pc = make_pc()
    before = worldfs.read_yaml(wroot / "state" / "party" / f"{pc}.yaml")["gold"]
    res = runner.invoke(app, ["gold", "spend", "--amount", "-5", "--actor", pc])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "bad_amount"
    after = worldfs.read_yaml(wroot / "state" / "party" / f"{pc}.yaml")["gold"]
    assert after == before


def test_gold_add_negative_amount_rejected(wroot):
    pc = make_pc()
    res = runner.invoke(app, ["gold", "add", "--amount", "-5", "--actor", pc])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "bad_amount"
