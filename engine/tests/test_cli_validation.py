"""CLI-level input validation: malformed options must produce clean JSON
error envelopes, never raw Python tracebacks."""
import json

from typer.testing import CliRunner

from ttrpg_engine.cli import app
from conftest import make_pc

runner = CliRunner()


def _err(res):
    assert res.exit_code == 1, res.stdout
    return json.loads(res.stdout)["error"]["code"]


def test_char_create_bad_assign_is_clean_error(wroot):
    # "DEX=--15" passed the old digit check then threw an uncaught ValueError
    res = runner.invoke(app, ["char", "create", "--name", "X", "--class", "fighter",
                              "--race", "human", "--assign", "DEX=--15,CON=14",
                              "--skills", "athletics"])
    assert _err(res) == "bad_assign"


def test_char_create_nonnumeric_assign_is_clean_error(wroot):
    res = runner.invoke(app, ["char", "create", "--name", "X", "--class", "fighter",
                              "--race", "human", "--assign", "DEX=high",
                              "--skills", "athletics"])
    assert _err(res) == "bad_assign"


def test_move_bad_coord(wroot):
    make_pc()
    runner.invoke(app, ["--seed", "5", "encounter", "start", "maps/encounters/skirmish.yaml"])
    res = runner.invoke(app, ["move", "--actor", "pc-borin", "--to", "notacoord"])
    assert _err(res) == "bad_coord"


def test_cast_bad_at(wroot):
    make_pc()
    runner.invoke(app, ["--seed", "5", "encounter", "start", "maps/encounters/skirmish.yaml"])
    res = runner.invoke(app, ["cast", "--caster", "pc-borin", "--spell", "sacred_flame",
                              "--at", "9"])
    assert _err(res) == "bad_coord"


def test_quest_offer_bad_hour(wroot):
    make_pc()
    res = runner.invoke(app, ["quest", "offer", "--title", "T", "--desc", "d",
                              "--giver", "world", "--spawn", "--gold", "1",
                              "--deadline", "1203-04-20", "--deadline-hour", "99"])
    assert _err(res) == "bad_hour"
