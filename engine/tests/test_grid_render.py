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
    grid_rows = art.split("\n\n")[0]                 # rows only, not the legend block
    assert "B" in grid_rows and "g" in grid_rows
    assert "#" in grid_rows and "~" in grid_rows     # real wall + difficult cells drawn
    assert "B=pc-brin" in art and "g=goblin-1" in art
    row1 = art.splitlines()[2]        # header is line 0, row y=0 is line 1
    assert row1.split()[1:][1] == "B"  # x=1 on row y=1


def test_dead_monster_dropped_from_legend():
    # a dead monster leaves the board, so it must leave the legend too
    enc = {**ENC, "order": ["pc-brin", "goblin-1", "goblin-2"],
           "positions": {"pc-brin": [1, 1], "goblin-2": [5, 2]},
           "monsters": {"goblin-1": {"name": "Goblin 1", "hp": 0, "dead": True},
                        "goblin-2": {"name": "Goblin 2", "hp": 7, "dead": False}}}
    art = render.ascii_map(enc)
    assert "goblin-2" in art          # living combatant still keyed
    assert "goblin-1" not in art      # dead one gone from the legend


def test_cli_render(wroot):
    worldfs.write_yaml(wroot / "state" / "encounter.yaml", ENC)
    res = runner.invoke(app, ["map", "render"])
    data = json.loads(res.stdout)
    assert data["round"] == 1 and data["turn"] == "pc-brin"
    assert "#" in data["map"].split("\n\n")[0]        # wall drawn in the grid, not just the legend


def test_cli_render_no_encounter(wroot):
    res = runner.invoke(app, ["map", "render"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "no_encounter"


def test_symbols_collision_walks_alphabet():
    enc = {
        "order": ["pc-brin", "pc-borin", "goblin-1", "gnoll-1"],
        "grid": {"width": 4, "height": 2},
        "terrain": [],
        "positions": {},
        "monsters": {"goblin-1": {}, "gnoll-1": {}},
    }
    syms = render.symbols(enc)
    assert syms["pc-brin"] == "B"
    assert syms["pc-borin"] == "C"      # collision walked B -> C
    assert syms["goblin-1"] == "g"
    assert syms["gnoll-1"] == "h"       # collision walked g -> h
    assert len(set(syms.values())) == 4  # all glyphs unique


def test_symbols_bounded_fallback_beyond_26():
    # 30 monsters all starting with the same letter must not loop forever and
    # must still get unique glyphs (letters exhausted -> fallback pool)
    enc = {"order": [f"goblin-{i}" for i in range(1, 31)],
           "grid": {"width": 4, "height": 2}, "terrain": [], "positions": {},
           "monsters": {f"goblin-{i}": {} for i in range(1, 31)}}
    syms = render.symbols(enc)
    assert len(syms) == 30
    assert len(set(syms.values())) == 30    # every combatant got a distinct glyph
