import re
from dataclasses import dataclass
from random import Random

_DICE_RE = re.compile(r"^(\d*)d(\d+)([+-]\d+)?$")
_MAX_COUNT = 1000   # bound allocation: `999999d6` should not build a huge list
_MAX_SIDES = 1000  # cap die faces for the same reason


@dataclass
class RollResult:
    expr: str
    rolls: list[int]
    modifier: int
    total: int


def parse(expr: str) -> tuple[int, int, int]:
    m = _DICE_RE.match(expr.strip().lower())
    if not m:
        raise ValueError(f"invalid dice expression: {expr!r}")
    count = int(m.group(1) or 1)
    sides = int(m.group(2))
    modifier = int(m.group(3) or 0)
    if count < 1 or sides < 2:
        raise ValueError(f"invalid dice expression: {expr!r}")
    if count > _MAX_COUNT or sides > _MAX_SIDES:
        raise ValueError(
            f"dice expression too large: {expr!r} (max {_MAX_COUNT}d{_MAX_SIDES})")
    return count, sides, modifier


def roll(expr: str, rng: Random) -> RollResult:
    count, sides, modifier = parse(expr)
    rolls = [rng.randint(1, sides) for _ in range(count)]
    return RollResult(expr, rolls, modifier, sum(rolls) + modifier)
