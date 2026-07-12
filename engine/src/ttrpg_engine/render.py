from pathlib import Path

from ttrpg_engine import grid, worldfs
from ttrpg_engine.errors import EngineError


def load_encounter(root: Path) -> dict:
    path = root / "state" / "encounter.yaml"
    if not path.exists():
        raise EngineError("no_encounter", "no active encounter")
    return worldfs.read_yaml(path)


def symbols(enc: dict) -> dict[str, str]:
    """Deterministic map of combatant id -> single glyph."""
    out, used = {}, set()
    for cid in enc["order"]:
        is_pc = cid.startswith("pc-")
        glyph = cid.removeprefix("pc-")[0]
        glyph = glyph.upper() if is_pc else glyph.lower()
        while glyph in used:  # collision: walk the alphabet
            nxt = chr(ord(glyph) + 1)
            glyph = nxt if nxt.isalpha() else ("A" if is_pc else "a")
        used.add(glyph)
        out[cid] = glyph
    return out


def ascii_map(enc: dict) -> str:
    w, h = enc["grid"]["width"], enc["grid"]["height"]
    syms = symbols(enc)
    cells = [["." for _ in range(w)] for _ in range(h)]
    for x, y in grid.cells_of(enc, "wall"):
        cells[y][x] = "#"
    for x, y in grid.cells_of(enc, "difficult"):
        cells[y][x] = "~"
    for cid, pos in enc["positions"].items():
        if enc["monsters"].get(cid, {}).get("dead", False):
            continue
        x, y = pos
        cells[y][x] = syms[cid]
    header = "   " + " ".join(str(x % 10) for x in range(w))
    rows = [f"{y:2d} " + " ".join(cells[y]) for y in range(h)]
    legend = "  ".join(f"{glyph}={cid}" for cid, glyph in syms.items())
    return "\n".join([header, *rows, "", legend, "#=wall  ~=difficult"])
