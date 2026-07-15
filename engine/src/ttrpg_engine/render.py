from pathlib import Path
from xml.sax.saxutils import escape

from ttrpg_engine import grid, worldfs
from ttrpg_engine.errors import EngineError

_CELL = 40


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
    for x, y in grid.cells_of(enc, "dark"):
        cells[y][x] = ":"
    for x, y in grid.cells_of(enc, "difficult"):
        cells[y][x] = "~"
    for x, y in grid.cells_of(enc, "wall"):
        cells[y][x] = "#"
    for cid, pos in enc["positions"].items():
        if enc["monsters"].get(cid, {}).get("dead", False):
            continue
        x, y = pos
        cells[y][x] = syms[cid]
    header = "   " + " ".join(str(x % 10) for x in range(w))
    rows = [f"{y:2d} " + " ".join(cells[y]) for y in range(h)]
    legend = "  ".join(f"{glyph}={cid}" for cid, glyph in syms.items())
    key = "#=wall  ~=difficult  :=dark" + ("  (the whole map is dark)" if enc.get("dark") else "")
    return "\n".join([header, *rows, "", legend, key])


def svg_map(enc: dict) -> str:
    w, h = enc["grid"]["width"], enc["grid"]["height"]
    W, H = w * _CELL, h * _CELL + 30
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
             f'viewBox="0 0 {W} {H}" font-family="monospace">',
             f'<rect width="{W}" height="{H}" fill="#fafaf7"/>']
    for x, y in grid.cells_of(enc, "difficult"):
        parts.append(f'<rect x="{x*_CELL}" y="{y*_CELL}" width="{_CELL}" height="{_CELL}" fill="#d8c9a3"/>')
    for x, y in grid.cells_of(enc, "dark"):
        parts.append(f'<rect x="{x*_CELL}" y="{y*_CELL}" width="{_CELL}" height="{_CELL}" fill="#6b7280" opacity="0.55"/>')
    for x, y in grid.cells_of(enc, "wall"):
        parts.append(f'<rect x="{x*_CELL}" y="{y*_CELL}" width="{_CELL}" height="{_CELL}" fill="#44403c"/>')
    for i in range(w + 1):
        parts.append(f'<line x1="{i*_CELL}" y1="0" x2="{i*_CELL}" y2="{h*_CELL}" stroke="#ccc"/>')
    for i in range(h + 1):
        parts.append(f'<line x1="0" y1="{i*_CELL}" x2="{w*_CELL}" y2="{i*_CELL}" stroke="#ccc"/>')
    syms = symbols(enc)
    for cid, pos in enc["positions"].items():
        if enc["monsters"].get(cid, {}).get("dead", False):
            continue
        x, y = pos
        cx, cy = x * _CELL + _CELL // 2, y * _CELL + _CELL // 2
        color = "#2563eb" if cid.startswith("pc-") else "#dc2626"
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="{_CELL//2 - 4}" fill="{color}"/>')
        parts.append(f'<text x="{cx}" y="{cy + 5}" text-anchor="middle" fill="#fff">{escape(syms[cid])}</text>')
    # names and ids are world/game-author content; escape so the SVG string
    # is safe to drop into innerHTML in the live viewer
    legend = "   ".join(f"{escape(s)}={escape(cid)}" for cid, s in syms.items())
    parts.append(f'<text x="4" y="{h*_CELL + 20}" font-size="12">{escape(str(enc["name"]))} — round {enc["round"]} — {legend}</text>')
    parts.append("</svg>")
    return "".join(parts)


def write_svg(root: Path, enc: dict) -> Path:
    clk = worldfs.read_yaml(worldfs.state(root, "clock"))
    stem = f'{clk["date"]}-{enc["id"]}-r{enc["round"]:02d}'
    out = root / "renders" / f"{stem}.svg"
    out.parent.mkdir(exist_ok=True)
    out.write_text(svg_map(enc))
    entries = [f'<h3>{f.stem}</h3><img src="{f.name}" style="max-width:100%">'
               for f in sorted(out.parent.glob("*.svg"), reverse=True)]
    (out.parent / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>Battle maps</title>'
        '<body style="font-family:monospace;max-width:720px;margin:2rem auto">'
        + "".join(entries) + "</body>")
    return out
