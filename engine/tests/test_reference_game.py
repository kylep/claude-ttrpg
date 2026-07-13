from pathlib import Path

from ttrpg_engine import game

REFERENCE = Path(__file__).resolve().parents[2] / "games" / "reference"


def test_reference_game_validates():
    assert REFERENCE.exists(), "games/reference missing"
    assert game.validate(REFERENCE) == []


def test_reference_has_four_classes_and_races():
    g = game.load(REFERENCE)
    assert set(g["classes"]) == {"fighter", "rogue", "cleric", "wizard"}
    assert set(g["races"]) == {"human", "elf", "dwarf", "halfling"}
    for cls in g["classes"].values():
        assert set(cls["levels"]) == {1, 2, 3}
