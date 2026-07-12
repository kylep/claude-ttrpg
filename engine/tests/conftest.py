from pathlib import Path

import pytest

from ttrpg_engine import worldfs

FIXTURE_GAME = Path(__file__).parent / "fixtures" / "minigame"


@pytest.fixture
def wroot(tmp_path, monkeypatch):
    root = tmp_path / "testworld"
    worldfs.init_world(root, FIXTURE_GAME, "Test World")
    monkeypatch.chdir(root)
    return root
