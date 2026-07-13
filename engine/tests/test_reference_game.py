from pathlib import Path

import pytest

from ttrpg_engine import game

REFERENCE = Path(__file__).resolve().parents[2] / "games" / "reference"

_MISSING_FEATURES_REASON = "features.yaml lands with content task"


@pytest.mark.xfail(reason=_MISSING_FEATURES_REASON, strict=False)
def test_reference_game_validates():
    assert REFERENCE.exists(), "games/reference missing"
    assert game.validate(REFERENCE) == []


@pytest.mark.xfail(reason=_MISSING_FEATURES_REASON, strict=False)
def test_reference_has_four_classes_and_races():
    g = game.load(REFERENCE)
    assert set(g["classes"]) == {"fighter", "rogue", "cleric", "wizard"}
    assert set(g["races"]) == {"human", "elf", "dwarf", "halfling"}
    for cls in g["classes"].values():
        assert set(cls["levels"]) == {1, 2, 3}
