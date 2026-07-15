import json
import random

import pytest
from typer.testing import CliRunner

from ttrpg_engine import dice
from ttrpg_engine.cli import app

runner = CliRunner()


def test_parse():
    assert dice.parse("2d6+3") == (2, 6, 3)
    assert dice.parse("d20") == (1, 20, 0)
    assert dice.parse("1d8-1") == (1, 8, -1)


@pytest.mark.parametrize("bad", ["", "d", "0d6", "2d1", "1d6+", "banana"])
def test_parse_rejects(bad):
    with pytest.raises(ValueError):
        dice.parse(bad)


@pytest.mark.parametrize("huge", ["999999d6", "1001d6", "2d99999", "1d1001"])
def test_parse_rejects_oversized(huge):
    # cap count/sides so a huge expression can't allocate a giant list
    with pytest.raises(ValueError):
        dice.parse(huge)


def test_cli_roll_oversized_is_json_error():
    res = runner.invoke(app, ["roll", "999999d6"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "bad_expr"


def test_roll_bounds():
    rng = random.Random(1)
    r = dice.roll("4d6+2", rng)
    assert len(r.rolls) == 4
    assert all(1 <= x <= 6 for x in r.rolls)
    assert r.total == sum(r.rolls) + 2


def test_cli_roll_vs():
    res = runner.invoke(app, ["--seed", "7", "roll", "d20+5", "--vs", "14"])
    assert res.exit_code == 0
    data = json.loads(res.stdout)
    assert data["total"] == data["rolls"][0] + 5
    assert data["success"] == (data["total"] >= 14)
    assert data["crit"] in (None, "hit", "fumble")


def test_cli_roll_bad_expr_is_json_error():
    res = runner.invoke(app, ["roll", "banana"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "bad_expr"
