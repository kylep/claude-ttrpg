import json

from typer.testing import CliRunner

from ttrpg_engine import clock, timeline, worldfs
from ttrpg_engine.cli import app

runner = CliRunner()


def test_clock_advance_rolls_days_and_months():
    c = {"date": "1203-04-29", "hour": 20}
    c2 = clock.advance(c, 10)
    assert c2 == {"date": "1203-04-30", "hour": 6}
    c3 = clock.advance(c2, 24 * 1)
    assert c3["date"] == "1203-05-01"


def test_append_event_ids_increment(wroot):
    e1 = timeline.append_event(wroot, type_="gold", summary="found 5gp")
    e2 = timeline.append_event(wroot, type_="gold", summary="found 2gp")
    assert e1 == "1203-04-17-001"
    assert e2 == "1203-04-17-002"
    data = worldfs.read_yaml(wroot / "timeline" / f"{e2}.yaml")
    assert data["type"] == "gold" and data["session"] == 0 and data["override"] is False


def test_session_start_and_override_log(wroot):
    res = runner.invoke(app, ["session", "start"])
    assert json.loads(res.stdout) == {"session": 1}
    assert (wroot / "sessions" / "session-001").is_dir()
    res = runner.invoke(app, ["override", "log", "--summary", "GM fiat: gate is open"])
    ev = json.loads(res.stdout)["event"]
    data = worldfs.read_yaml(wroot / "timeline" / f"{ev}.yaml")
    assert data["override"] is True and data["session"] == 1
