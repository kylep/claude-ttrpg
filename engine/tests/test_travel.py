import json

from typer.testing import CliRunner

from ttrpg_engine import worldfs
from ttrpg_engine.cli import app

runner = CliRunner()


def test_travel_moves_party_and_clock(wroot):
    res = runner.invoke(app, ["travel", "--to", "cave"])
    assert res.exit_code == 0, res.stdout
    data = json.loads(res.stdout)
    assert data["from"] == "town" and data["to"] == "cave" and data["hours"] == 4
    party = worldfs.read_yaml(wroot / "state" / "party.yaml")
    assert party["location"] == "cave"
    assert worldfs.read_yaml(wroot / "state" / "clock.yaml")["hour"] == 13


def test_travel_rejects_unconnected_and_unknown(wroot):
    res = runner.invoke(app, ["travel", "--to", "atlantis"])
    assert json.loads(res.stdout)["error"]["code"] == "unknown_node"
    runner.invoke(app, ["travel", "--to", "cave"])
    res = runner.invoke(app, ["travel", "--to", "cave"])
    assert json.loads(res.stdout)["error"]["code"] == "no_route"
