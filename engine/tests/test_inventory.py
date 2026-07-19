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


def test_gold_reason_lands_in_timeline(wroot):
    pc = make_pc()
    res = runner.invoke(app, ["gold", "spend", "--amount", "1", "--actor", pc,
                              "--reason", "a round for the taproom"])
    assert res.exit_code == 0, res.stdout
    summaries = [worldfs.read_yaml(p)["summary"]
                 for p in (wroot / "timeline").glob("*.yaml")]
    assert any("spends 1 gp (a round for the taproom)" in s for s in summaries)
    # no --reason -> the old summary shape, no trailing parens
    runner.invoke(app, ["gold", "add", "--amount", "2", "--actor", pc])
    summaries = [worldfs.read_yaml(p)["summary"]
                 for p in (wroot / "timeline").glob("*.yaml")]
    assert any(s.endswith("gains 2 gp") for s in summaries)


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


def test_buy_decrements_gold_and_adds_item(wroot):
    pc = make_pc()  # fighter, gold 10
    res = runner.invoke(app, ["buy", "--actor", pc, "--item", "dagger", "--qty", "2"])
    assert res.exit_code == 0, res.stdout
    data = json.loads(res.stdout)
    assert data["spent"] == 4 and data["gold"] == 6 and data["gold_source"] == pc
    sheet = worldfs.read_yaml(wroot / "state" / "party" / f"{pc}.yaml")
    assert sheet["gold"] == 6
    assert {"item": "dagger", "qty": 2} in sheet["inventory"]


def test_buy_insufficient_gold_rejected_and_atomic(wroot):
    pc = make_pc()
    res = runner.invoke(app, ["buy", "--actor", pc, "--item", "longsword", "--qty", "5"])  # 75 > 10
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "no_gold"
    sheet = worldfs.read_yaml(wroot / "state" / "party" / f"{pc}.yaml")
    assert sheet["gold"] == 10  # untouched
    longsword = next(l for l in sheet["inventory"] if l["item"] == "longsword")
    assert longsword["qty"] == 1  # nothing added


def test_buy_party_spends_pool_item_goes_to_actor(wroot):
    pc = make_pc()
    runner.invoke(app, ["gold", "add", "--amount", "50", "--party"])
    res = runner.invoke(app, ["buy", "--actor", pc, "--item", "dagger", "--party"])
    assert res.exit_code == 0, res.stdout
    data = json.loads(res.stdout)
    assert data["gold_source"] == "party" and data["gold"] == 48
    assert worldfs.read_yaml(wroot / "state" / "party.yaml")["gold"] == 48
    sheet = worldfs.read_yaml(wroot / "state" / "party" / f"{pc}.yaml")
    assert {"item": "dagger", "qty": 1} in sheet["inventory"]  # item lands with the actor
    assert sheet["gold"] == 10  # actor purse untouched
