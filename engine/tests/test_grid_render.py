import json

from typer.testing import CliRunner

from ttrpg_engine import grid, render, worldfs
from ttrpg_engine.cli import app

runner = CliRunner()

ENC = {
    "id": "skirmish", "name": "Skirmish", "round": 1, "turn": 0,
    "order": ["pc-brin", "goblin-1"],
    "grid": {"width": 6, "height": 4},
    "terrain": [{"type": "wall", "cells": [[3, 0], [3, 1]]},
                {"type": "difficult", "cells": [[4, 3]]}],
    "positions": {"pc-brin": [1, 1], "goblin-1": [5, 2]},
    "monsters": {"goblin-1": {"type": "goblin", "name": "Goblin 1", "hp": 7, "dead": False}},
}


def test_chebyshev():
    assert grid.chebyshev((0, 0), (3, 4)) == 4
    assert grid.chebyshev((2, 2), (2, 2)) == 0


def test_blocked():
    assert grid.blocked(ENC, (3, 0)) == "wall"
    assert grid.blocked(ENC, (6, 0)) == "oob"
    assert grid.blocked(ENC, (5, 2)) == "occupied"
    assert grid.blocked(ENC, (0, 0)) is None


def test_ascii_map_contents():
    art = render.ascii_map(ENC)
    assert "B" in art and "g" in art and "#" in art and "~" in art
    assert "B=pc-brin" in art and "g=goblin-1" in art
    row1 = art.splitlines()[2]        # header is line 0, row y=0 is line 1
    assert row1.split()[1:][1] == "B"  # x=1 on row y=1


def test_cli_render(wroot):
    worldfs.write_yaml(wroot / "state" / "encounter.yaml", ENC)
    res = runner.invoke(app, ["map", "render"])
    data = json.loads(res.stdout)
    assert data["round"] == 1 and data["turn"] == "pc-brin"
    assert "#" in data["map"]


def test_cli_render_no_encounter(wroot):
    res = runner.invoke(app, ["map", "render"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "no_encounter"
