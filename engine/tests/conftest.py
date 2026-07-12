from pathlib import Path

import pytest
from typer.testing import CliRunner

from ttrpg_engine import worldfs

FIXTURE_GAME = Path(__file__).parent / "fixtures" / "minigame"

_runner = CliRunner()


@pytest.fixture
def wroot(tmp_path, monkeypatch):
    root = tmp_path / "testworld"
    worldfs.init_world(root, FIXTURE_GAME, "Test World")
    monkeypatch.chdir(root)
    return root


def make_pc(name="Borin", cls="fighter", race="dwarf",
            assign="STR=15,CON=14,DEX=13,WIS=12,INT=10,CHA=8",
            skills="athletics,perception"):
    from ttrpg_engine.cli import app
    res = _runner.invoke(app, ["char", "create", "--name", name, "--class", cls,
                               "--race", race, "--assign", assign, "--skills", skills])
    assert res.exit_code == 0, res.stdout
    return f"pc-{name.lower()}"
