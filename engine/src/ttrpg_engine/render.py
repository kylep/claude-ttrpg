from pathlib import Path
from xml.sax.saxutils import escape

from ttrpg_engine import grid, worldfs
from ttrpg_engine.errors import EngineError

_CELL = 40  # pixel size of one grid square in the rendered SVG

# terrain fill palette, shared by the SVG renderer and the viewer's terrain
# legend so a swatch always matches the square it explains. Colours are chosen
# to read clearly against the parchment ground and apart from the blue/red
# combatant tokens: a warm amber for difficult ground (was a washed-out tan
# too close to the background), slate for darkness, near-black for walls.
TERRAIN_STYLE = {
    "difficult": {"fill": "#d59f3c", "opacity": 1.0, "label": "difficult ground"},
    "dark":      {"fill": "#4b5563", "opacity": 0.6, "label": "darkness"},
    "wall":      {"fill": "#3a352f", "opacity": 1.0, "label": "wall"},
}


def terrain_legend(enc: dict) -> list[dict]:
    """The terrain types actually present on this map, each as {type, color,
    label} — the key the viewer renders beside the map so its colours read
    clearly. Only present types are returned; a map-wide `dark` also counts as
    darkness. Ordered difficult, darkness, wall (background to foreground)."""
    out = []
    for t in ("difficult", "dark", "wall"):
        present = bool(grid.cells_of(enc, t)) or (t == "dark" and enc.get("dark"))
        if present:
            style = TERRAIN_STYLE[t]
            out.append({"type": t, "color": style["fill"], "label": style["label"]})
    return out


def load_encounter(root: Path) -> dict:
    path = root / "state" / "encounter.yaml"
    if not path.exists():
        raise EngineError("no_encounter", "no active encounter")
    return worldfs.read_yaml(path)


_GLYPH_FALLBACK = "0123456789@%&*+=<>"  # once a case's 26 letters are all taken


def _pick_glyph(name: str, is_pc: bool, used: set) -> str:
    """One unused glyph for `name`. PCs first try each distinct letter of their
    own name in order (so the token letter matches the player, and a shared
    first initial falls through to the next real letter of the name — Brin=B,
    Borin=O — rather than a stranger's letter); then both PCs and monsters walk
    the alphabet from the first initial, and finally spill into the fallback
    pool. Case keeps PC letters (upper) distinct from monsters (lower)."""
    def cased(c: str) -> str:
        return c.upper() if is_pc else c.lower()
    if is_pc:  # prefer a letter the player actually has in their name
        for ch in name:
            if ch.isalpha() and cased(ch) not in used:
                return cased(ch)
    first = next((c for c in name if c.isalpha()), "a")
    glyph = cased(first)
    tries = 0
    while glyph in used and tries < 26:  # collision: walk the alphabet, bounded
        nxt = chr(ord(glyph) + 1)
        glyph = nxt if nxt.isalpha() else ("A" if is_pc else "a")
        tries += 1
    if glyph in used:  # every letter of this case is taken — fall back
        glyph = next((c for c in _GLYPH_FALLBACK if c not in used), "?")
    return glyph


def symbols(enc: dict) -> dict[str, str]:
    """Deterministic map of combatant id -> single glyph, unique per encounter."""
    out, used = {}, set()
    for cid in enc["order"]:
        is_pc = cid.startswith("pc-")
        name = cid.removeprefix("pc-") if is_pc else cid
        glyph = _pick_glyph(name, is_pc, used)
        used.add(glyph)
        out[cid] = glyph
    return out


def _drawn(enc: dict, cid: str) -> bool:
    """A combatant is on the board unless it's a dead monster. The dead leave
    the map, so they leave the legend/caption too — no dangling glyph key."""
    return not enc["monsters"].get(cid, {}).get("dead", False)


def ascii_map(enc: dict) -> str:
    """Text battle map with a coordinate frame, terrain glyphs (#/~/:), and one
    glyph per living combatant; the dead are omitted. Ends with legend + key."""
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
    legend = "  ".join(f"{glyph}={cid}" for cid, glyph in syms.items()
                       if _drawn(enc, cid))
    key = "#=wall  ~=difficult  :=dark" + ("  (the whole map is dark)" if enc.get("dark") else "")
    return "\n".join([header, *rows, "", legend, key])


# conditions that read as "something is wrong with this combatant" — the token
# gets a warning pip; the roster carries the specifics
_BAD_EFFECTS = frozenset({"poisoned", "prone", "grappled", "restrained",
                          "frightened", "unconscious", "dying", "weakened"})


def _hp_stroke(frac: float | None) -> str:
    """Ring colour for a health fraction: moss / gold / blood. None (unknown
    health, e.g. a PC on a standalone map) falls through to a neutral edge."""
    if frac is None:
        return "#7c6f5a"
    if frac > 2 / 3:
        return "#5f8a3f"
    if frac > 1 / 3:
        return "#b98a2e"
    return "#b8453c"


def _enc_status(enc: dict) -> dict:
    """Per-token status derivable from the encounter alone: monster health and
    conditions plus hidden. PC health/effects live in sheets, so the live
    viewer passes a richer overlay; standalone/exported maps use this."""
    aloft = enc.get("aloft", {})
    status = {}
    for cid in enc["positions"]:
        mon = enc["monsters"].get(cid)
        if not mon:
            status[cid] = {"hp_frac": None, "dead": False, "hidden": False,
                           "bad": False, "aloft": bool(aloft.get(cid))}
            continue
        mx = mon.get("max_hp") or 1
        names = {e["name"] for e in mon.get("effects", [])}
        status[cid] = {
            "hp_frac": None if mon.get("dead") else mon["hp"] / mx,
            "dead": bool(mon.get("dead")),
            "hidden": "hidden" in names,
            "bad": bool(names & _BAD_EFFECTS),
            "aloft": bool(aloft.get(cid)),
        }
    return status


def _caption_lines(enc: dict, syms: dict, max_chars: int) -> list[str]:
    """The bottom caption, wrapped to the map width so long rosters don't run
    off the right edge (they used to clip). All fields escaped — author text."""
    head = f'{escape(str(enc["name"]))} — round {enc["round"]} — '
    items = [f"{escape(s)}={escape(cid)}" for cid, s in syms.items()
             if _drawn(enc, cid)]
    lines, cur = [], head
    for it in items:
        sep = "" if cur.endswith("— ") else "   "
        if len(cur) + len(sep) + len(it) > max_chars and cur.strip() and cur != head:
            lines.append(cur)
            cur = "      " + it            # continuation indent
        else:
            cur += sep + it
    lines.append(cur)
    return lines


def svg_map(enc: dict, *, caption: bool = True, status: dict | None = None,
            up: str | None = None) -> str:
    """Battle map as an SVG string.

    caption — draw the name/round/legend footer (on for standalone/exported
        maps; the live viewer turns it off and renders its own HTML legend).
    status — {cid: {hp_frac, dead, hidden, bad}} overlay; the viewer supplies
        it so PC tokens get health rings and condition pips too. Defaults to
        what the encounter alone reveals (monsters only).
    up — the combatant whose turn it is, highlighted; derived from the
        encounter when not given (the viewer passes an already-masked value).
    """
    w, h = enc["grid"]["width"], enc["grid"]["height"]
    if up is None and enc.get("order") and 0 <= enc.get("turn", -1) < len(enc["order"]):
        up = enc["order"][enc["turn"]]
    st_map = status if status is not None else _enc_status(enc)

    syms = symbols(enc)
    cap_lines = _caption_lines(enc, syms, max(20, w * _CELL // 7)) if caption else []
    W = w * _CELL
    H = h * _CELL + (10 + 15 * len(cap_lines) if caption else 0)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
             f'viewBox="0 0 {W} {H}" font-family="monospace">',
             f'<rect width="{W}" height="{H}" fill="#fafaf7"/>']
    for kind in ("difficult", "dark", "wall"):
        style = TERRAIN_STYLE[kind]
        op = f' opacity="{style["opacity"]}"' if style["opacity"] != 1.0 else ""
        for x, y in grid.cells_of(enc, kind):
            parts.append(f'<rect x="{x*_CELL}" y="{y*_CELL}" width="{_CELL}" '
                         f'height="{_CELL}" fill="{style["fill"]}"{op}/>')
    for i in range(w + 1):
        parts.append(f'<line x1="{i*_CELL}" y1="0" x2="{i*_CELL}" y2="{h*_CELL}" stroke="#ccc"/>')
    for i in range(h + 1):
        parts.append(f'<line x1="0" y1="{i*_CELL}" x2="{w*_CELL}" y2="{i*_CELL}" stroke="#ccc"/>')

    # whose-turn cell tint, drawn under the tokens
    if up in enc["positions"]:
        ux, uy = enc["positions"][up]
        parts.append(f'<rect x="{ux*_CELL}" y="{uy*_CELL}" width="{_CELL}" height="{_CELL}" '
                     f'fill="#d9973b" opacity="0.28"/>')
        parts.append(f'<rect x="{ux*_CELL+1}" y="{uy*_CELL+1}" width="{_CELL-2}" height="{_CELL-2}" '
                     f'fill="none" stroke="#d9973b" stroke-width="2"/>')

    r = _CELL // 2 - 4
    for cid, pos in enc["positions"].items():
        if enc["monsters"].get(cid, {}).get("dead", False):
            continue  # the dead leave the board
        x, y = pos
        cx, cy = x * _CELL + _CELL // 2, y * _CELL + _CELL // 2
        st = st_map.get(cid, {})
        fill = "#2563eb" if cid.startswith("pc-") else "#dc2626"
        ring = _hp_stroke(st.get("hp_frac"))
        dash = ' stroke-dasharray="3 2"' if st.get("hidden") else ""
        parts.append(f'<circle class="tok" cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" '
                     f'stroke="{ring}" stroke-width="3"{dash}/>')
        parts.append(f'<text x="{cx}" y="{cy + 5}" text-anchor="middle" fill="#fff">{escape(syms[cid])}</text>')
        if st.get("aloft"):   # a caret riding above the token
            parts.append(f'<text x="{cx - r}" y="{cy - r + 2}" font-size="13" fill="#c9a86a">▲</text>')
        if st.get("bad"):     # a warning pip; the roster names the condition
            parts.append(f'<circle cx="{cx + r - 1}" cy="{cy - r + 1}" r="4" fill="#b8453c" stroke="#fff" stroke-width="1"/>')
        if st.get("hidden"):
            parts.append(f'<text x="{cx + r - 4}" y="{cy + r + 4}" font-size="12" fill="#3f3a33">?</text>')

    # names and ids are world/game-author content; escape so the SVG string
    # is safe to drop into innerHTML in the live viewer
    for i, line in enumerate(cap_lines):
        parts.append(f'<text x="4" y="{h*_CELL + 16 + 15*i}" font-size="12">{line}</text>')
    parts.append("</svg>")
    return "".join(parts)


def write_svg(root: Path, enc: dict) -> Path:
    """Write the current round's map to renders/ (named date-id-round) and
    regenerate renders/index.html as a newest-first gallery of every map."""
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
