"""Region map renderer: the world map as a hand-drawn-feel SVG, generated
deterministically from canon/maps/region.yaml plus travel history.

Layout ruleset (proven against the ugliest case, a straight diagonal chain
into a corner):
- roads trim at icon edges, never through the art
- labels are placed by candidate scoring — left/right/above/below, each
  penalized for icon overlap, pennant overlap, road proximity, and frame
  overflow; the best spot wins
- furniture (compass, title cartouche) sizes itself from content and takes
  the emptiest corner

Lenses: the GM sees every node. Players get fog of war — visited nodes in
full, their unvisited neighbours as faint rumours ("Barrow Woods?"), and
everything beyond simply absent. Visited-ness derives from the game's start
location, the party's (and any split PC's) current location, and the
timeline's travel events.
"""
import math
import random
import re
from pathlib import Path
from xml.sax.saxutils import escape

from ttrpg_engine import worldfs

_S = 64            # px per region coordinate step
_MX, _MY = 110, 96  # map margins around the outermost nodes
_NODE_R = 30       # icon clearance radius: roads stop here, labels avoid it

_INK = "#4a3527"; _FAINT = "#8a7a5f"; _EMBER = "#a33d2f"; _PALE = "#efe6d2"
_PARCH = "#e8dcc0"; _BLOTCH = "#d8c9a6"

# summaries written by travel.go before events carried a structured delta
_TRAVEL_RE = re.compile(r"travels? (\S+) -> (\S+)")


def _region(root: Path) -> dict:
    return worldfs.read_yaml(root / "canon" / "maps" / "region.yaml")


def visited_nodes(root: Path, g: dict) -> set[str]:
    """Every node the party has ever stood on: the game's start location,
    current party/PC locations, and both ends of every travel event."""
    party = worldfs.read_yaml(worldfs.state(root, "party"))
    vis = {str(party["location"])}
    start = g["meta"].get("start_location")
    if start:
        vis.add(str(start))
    for pid in party["members"]:
        sheet = worldfs.read_yaml(worldfs.state(root, f"party/{pid}"))
        vis.add(str(worldfs.pc_location(sheet, party)))
    tl = root / "timeline"
    if tl.is_dir():
        for p in sorted(tl.glob("*.yaml")):
            ev = worldfs.read_yaml(p)
            if ev.get("type") != "travel":
                continue
            delta = ev.get("delta") or {}
            if delta.get("to"):
                vis.update({str(delta["to"]), str(delta.get("from", ""))})
            else:  # old worlds: recover the route from the summary text
                m = _TRAVEL_RE.search(ev.get("summary", ""))
                if m:
                    vis.update(m.groups())
    vis.discard("")
    return vis


# --- terrain icons -----------------------------------------------------------

def _trees(x, y):
    out = []
    for dx, dy, r in ((-13, 2, 9), (2, -7, 11), (14, 4, 8)):
        out.append(f'<circle cx="{x+dx}" cy="{y+dy-6}" r="{r}" fill="#6f7f52" stroke="{_INK}" stroke-width="1.6"/>')
        out.append(f'<line x1="{x+dx}" y1="{y+dy+3}" x2="{x+dx}" y2="{y+dy-4}" stroke="{_INK}" stroke-width="1.8"/>')
    return "".join(out)


def _houses(x, y):
    out = []
    for dx, dy, w in ((-16, 2, 14), (1, -4, 16), (14, 4, 12)):
        h = w * .7
        out.append(f'<rect x="{x+dx-w/2}" y="{y+dy-h/2}" width="{w}" height="{h}" fill="{_PALE}" stroke="{_INK}" stroke-width="1.6"/>')
        out.append(f'<path d="M{x+dx-w/2-2},{y+dy-h/2} L{x+dx},{y+dy-h/2-9} L{x+dx+w/2+2},{y+dy-h/2} Z" fill="#a3543c" stroke="{_INK}" stroke-width="1.6"/>')
    return "".join(out)


def _hills(x, y):
    return "".join(f'<path d="M{x+dx-16},{y+dy} Q{x+dx},{y+dy-18} {x+dx+16},{y+dy}" fill="none" stroke="{_INK}" stroke-width="1.9"/>'
                   for dx, dy in ((-12, 2), (12, 4), (0, 12)))


def _waves(x, y):
    return "".join(f'<path d="M{x-20},{y+dy} q6,-7 12,0 t12,0 t12,0" fill="none" stroke="#4a6a7a" stroke-width="2"/>'
                   for dy in (-6, 3, 12))


def _cave(x, y):
    return (f'<path d="M{x-16},{y+12} L{x-16},{y-2} Q{x},{y-20} {x+16},{y-2} L{x+16},{y+12} Z" fill="#c9bda3" stroke="{_INK}" stroke-width="1.8"/>'
            f'<path d="M{x-7},{y+12} L{x-7},{y+1} Q{x},{y-8} {x+7},{y+1} L{x+7},{y+12} Z" fill="#241c14"/>')


def _barrow(x, y):
    return (f'<path d="M{x-20},{y+10} Q{x},{y-18} {x+20},{y+10} Z" fill="#7d8a63" stroke="{_INK}" stroke-width="1.8"/>'
            f'<path d="M{x-5},{y+10} L{x-5},{y+2} Q{x},{y-3} {x+5},{y+2} L{x+5},{y+10} Z" fill="#241c14"/>'
            f'<line x1="{x}" y1="{y-16}" x2="{x}" y2="{y-26}" stroke="{_INK}" stroke-width="2"/>'
            f'<line x1="{x-4}" y1="{y-23}" x2="{x+4}" y2="{y-23}" stroke="{_INK}" stroke-width="2"/>')


def _signpost(x, y):
    return (f'<line x1="{x}" y1="{y+12}" x2="{x}" y2="{y-14}" stroke="{_INK}" stroke-width="2.4"/>'
            f'<path d="M{x-2},{y-13} h16 l5,4 l-5,4 h-16 Z" fill="{_PALE}" stroke="{_INK}" stroke-width="1.5"/>'
            f'<path d="M{x+2},{y-3} h-16 l-5,4 l5,4 h16 Z" fill="{_PALE}" stroke="{_INK}" stroke-width="1.5"/>')


def _cairn(x, y):
    """Fallback for terrain types the renderer doesn't know: a standing stone."""
    return (f'<path d="M{x-6},{y+12} L{x-8},{y-12} L{x},{y-16} L{x+8},{y-10} L{x+6},{y+12} Z" '
            f'fill="#b3a68a" stroke="{_INK}" stroke-width="1.8"/>')


_ICONS = {"settlement": _houses, "forest": _trees, "hills": _hills,
          "flooded": _waves, "underground": _cave, "sepulcher": _barrow,
          "road": _signpost}


# --- layout helpers ----------------------------------------------------------

def _seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == dy == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def _overlap(a, b):
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return max(0, w) * max(0, h)


def _rough_line(rng, x1, y1, x2, y2, seg=7):
    """A slightly wobbly path so roads feel drawn, not plotted."""
    pts = []
    for i in range(seg + 1):
        t = i / seg
        x, y = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
        if 0 < i < seg:
            x += rng.uniform(-2.2, 2.2)
            y += rng.uniform(-2.2, 2.2)
        pts.append(f"{x:.1f},{y:.1f}")
    return "M" + " L".join(pts)


def _label_pos(nid, text, pt, drawn_edges, W, party_at):
    """Candidate scoring: try left/right/above/below, penalize icon overlap,
    pennant overlap (party node only), road proximity, and frame overflow."""
    x, y = pt[nid]
    est = len(text) * 8.5
    icon = (x - 30, y - 30, x + 30, y + 26)
    pennant = (x + 16, y - 64, x + 150, y - 24) if nid == party_at else None
    best = None
    for dx, dy in ((-44, 5), (44, 5), (0, -42), (0, 44)):
        lx, ly = x + dx, y + dy
        left = lx - (est if dx < 0 else est / 2 if dx == 0 else 0)
        shift = 0
        if left < 34:
            shift = 34 - left
        if left + est > W - 34:
            shift = (W - 34) - (left + est)
        left += shift
        box = (left, ly - 13, left + est, ly + 4)
        pen = abs(shift) * .6 + _overlap(box, icon) * .5
        if pennant:
            pen += _overlap(box, pennant) * .5
        cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        for (ax, ay), (bx, by) in drawn_edges:
            d = _seg_dist(cx, cy, ax, ay, bx, by)
            if d < 26:
                pen += (26 - d) * 4
        if best is None or pen < best[0]:
            best = (pen, box[0], ly)
    return best[1], best[2]


# --- the renderer ------------------------------------------------------------

def svg(root: Path, g: dict, lens: str = "gm") -> str:
    lens = "gm" if lens == "gm" else "player"
    region = _region(root)
    nodes, edges = region["nodes"], region.get("edges", [])
    party = worldfs.read_yaml(worldfs.state(root, "party"))
    party_at = str(party["location"])

    vis = visited_nodes(root, g)
    neighbours = set()
    for e in edges:
        a, b = e["between"]
        if a in vis:
            neighbours.add(b)
        if b in vis:
            neighbours.add(a)
    if lens == "gm":
        shown, rumored = set(nodes), set()
    else:
        rumored = (neighbours - vis) & set(nodes)
        shown = (vis & set(nodes)) | rumored

    # frame extent from ALL nodes so the player map doesn't shrink-wrap and
    # leak how much world is out there beyond the fog
    W = max(n["coords"][0] for n in nodes.values()) * _S + 2 * _MX
    H = max(n["coords"][1] for n in nodes.values()) * _S + 2 * _MY + 30

    def pt(nid):
        cx, cy = nodes[nid]["coords"]
        return _MX + cx * _S, _MY + cy * _S

    pts = {nid: pt(nid) for nid in nodes}
    rng = random.Random(7)   # fixed seed: same world state -> same map

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
           f'font-family="Iowan Old Style, Palatino, Georgia, serif">']
    out.append(f'<rect width="{W}" height="{H}" fill="{_PARCH}"/>')
    for _ in range(26):
        bx, by, br = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(24, 90)
        out.append(f'<circle cx="{bx:.0f}" cy="{by:.0f}" r="{br:.0f}" fill="{_BLOTCH}" opacity="{rng.uniform(.12, .3):.2f}"/>')
    out.append(f'<rect x="14" y="14" width="{W-28}" height="{H-28}" fill="none" stroke="{_INK}" stroke-width="3"/>')
    out.append(f'<rect x="22" y="22" width="{W-44}" height="{H-44}" fill="none" stroke="{_INK}" stroke-width="1"/>')

    # roads: drawn when both ends are on the sheet and the party has stood on
    # at least one of them; trimmed to stop at the icons
    drawn_edges = []
    for e in edges:
        a, b = e["between"]
        if a not in nodes or b not in nodes:
            continue
        if lens != "gm" and not (a in shown and b in shown and (a in vis or b in vis)):
            continue
        (x1, y1), (x2, y2) = pts[a], pts[b]
        d = math.hypot(x2 - x1, y2 - y1) or 1
        ux, uy = (x2 - x1) / d, (y2 - y1) / d
        sx, sy = x1 + ux * _NODE_R, y1 + uy * _NODE_R
        ex, ey = x2 - ux * _NODE_R, y2 - uy * _NODE_R
        out.append(f'<path d="{_rough_line(rng, sx, sy, ex, ey)}" fill="none" stroke="{_INK}" '
                   f'stroke-width="2.2" stroke-dasharray="7 6" opacity=".75"/>')
        drawn_edges.append(((x1, y1), (x2, y2)))
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        out.append(f'<ellipse cx="{mx}" cy="{my}" rx="17" ry="11" fill="{_PARCH}" stroke="{_INK}" stroke-width="1.2"/>')
        out.append(f'<text x="{mx}" y="{my+4}" text-anchor="middle" font-size="11" fill="{_INK}">{e["hours"]}h</text>')

    for nid in nodes:
        if nid not in shown:
            continue
        x, y = pts[nid]
        name = str(nodes[nid].get("name", nid))
        icon = _ICONS.get(nodes[nid].get("terrain"), _cairn)(x, y)
        if nid in rumored:
            lx, ly = _label_pos(nid, name + "?", pts, drawn_edges, W, party_at)
            out.append(f'<g opacity=".42">{icon}</g>')
            out.append(f'<text x="{lx}" y="{ly}" font-size="14" font-style="italic" fill="{_FAINT}">{escape(name)}?</text>')
        else:
            lx, ly = _label_pos(nid, name, pts, drawn_edges, W, party_at)
            # visited nodes are live UI: the viewer opens their location card
            out.append(f'<g data-ref="{escape(nid)}" style="cursor:pointer">{icon}'
                       f'<text x="{lx}" y="{ly}" font-size="15" fill="{_INK}" font-weight="600" '
                       f'letter-spacing=".04em">{escape(name)}</text></g>')

    if party_at in pts and party_at in shown:
        px, py = pts[party_at]
        out.append(f'<line x1="{px+22}" y1="{py-12}" x2="{px+22}" y2="{py-44}" stroke="{_INK}" stroke-width="2.4"/>')
        out.append(f'<path d="M{px+22},{py-44} L{px+50},{py-37} L{px+22},{py-30} Z" fill="{_EMBER}" stroke="{_INK}" stroke-width="1.4"/>')
        out.append(f'<text x="{px+26}" y="{py-50}" font-size="11" fill="{_EMBER}" font-weight="700">YOU ARE HERE</text>')

    # compass takes whichever corner is farthest from every node
    corners = [(88, 96), (W - 88, 96), (88, H - 116), (W - 88, H - 116)]
    cx, cy = max(corners, key=lambda c: min(math.hypot(c[0] - p[0], c[1] - p[1]) for p in pts.values()))
    out.append(f'<circle cx="{cx}" cy="{cy}" r="30" fill="none" stroke="{_INK}" stroke-width="1.4"/>')
    out.append(f'<path d="M{cx},{cy-28} L{cx+7},{cy} L{cx},{cy+28} L{cx-7},{cy} Z" fill="{_INK}"/>')
    out.append(f'<path d="M{cx-28},{cy} L{cx},{cy-7} L{cx+28},{cy} L{cx},{cy+7} Z" fill="{_FAINT}"/>')
    out.append(f'<text x="{cx}" y="{cy-36}" text-anchor="middle" font-size="14" fill="{_INK}" font-weight="700">N</text>')

    # title cartouche sized from the world's name; breaks the frame cleanly
    title = str(worldfs.read_yaml(root / "world.yaml")["world"]).upper()
    tw = len(title) * (17 * .68 + 17 * .12)
    bw, bh = tw + 56, 40
    bx, by = W / 2 - bw / 2, H - 34 - bh / 2
    out.append(f'<rect x="{bx-10}" y="{by-6}" width="{bw+20}" height="{bh+12}" fill="{_PARCH}"/>')
    out.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" fill="{_PARCH}" stroke="{_INK}" stroke-width="2"/>')
    out.append(f'<rect x="{bx+5}" y="{by+5}" width="{bw-10}" height="{bh-10}" fill="none" stroke="{_INK}" stroke-width=".8"/>')
    out.append(f'<text x="{W/2}" y="{by+bh/2+6}" text-anchor="middle" font-size="17" fill="{_INK}" '
               f'font-weight="600" letter-spacing=".12em">{escape(title)}</text>')
    out.append('</svg>')
    return "".join(out)
