import json

from conftest import make_pc
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


def test_travel_pcs_full_roster_updates_party_location(wroot):
    make_pc(name="Borin")
    res = runner.invoke(app, ["travel", "--to", "cave", "--pcs", "pc-borin"])
    assert res.exit_code == 0, res.stdout
    party = worldfs.read_yaml(wroot / "state" / "party.yaml")
    # whole roster named by --pcs → the party's canonical location moves too
    assert party["location"] == "cave"
    assert worldfs.read_yaml(wroot / "state" / "party" / "pc-borin.yaml")["location"] == "cave"


def test_travel_pcs_subset_leaves_party_location(wroot):
    make_pc(name="Borin")
    make_pc(name="Ada")
    res = runner.invoke(app, ["travel", "--to", "cave", "--pcs", "pc-borin"])
    assert res.exit_code == 0, res.stdout
    party = worldfs.read_yaml(wroot / "state" / "party.yaml")
    # a genuine party split must NOT move the party's canonical location
    assert party["location"] == "town"
    assert worldfs.read_yaml(wroot / "state" / "party" / "pc-borin.yaml")["location"] == "cave"
