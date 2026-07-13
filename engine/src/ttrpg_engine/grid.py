import heapq


def chebyshev(a: tuple[int, int], b: tuple[int, int]) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def line_cells(a: tuple[int, int], b: tuple[int, int]) -> list[tuple[int, int]]:
    """Cells the segment between the centers of a and b passes through,
    excluding a, including b. Passing exactly through a corner steps
    diagonally (sight and shots slip between diagonal walls)."""
    (x, y), (x1, y1) = a, b
    nx, ny = abs(x1 - x), abs(y1 - y)
    sx, sy = (1 if x1 > x else -1), (1 if y1 > y else -1)
    ix = iy = 0
    cells = []
    while ix < nx or iy < ny:
        # compare (ix+0.5)/nx with (iy+0.5)/ny, cross-multiplied
        cross = (2 * ix + 1) * ny - (2 * iy + 1) * nx
        if cross <= 0 and ix < nx:
            x += sx
            ix += 1
        if cross >= 0 and iy < ny:
            y += sy
            iy += 1
        cells.append((x, y))
    return cells


def line_of_sight(enc: dict, a: tuple[int, int], b: tuple[int, int]) -> bool:
    """True if no wall cell lies strictly between a and b."""
    walls = cells_of(enc, "wall")
    return not any(c in walls for c in line_cells(tuple(a), tuple(b))[:-1])


def path_cost(enc: dict, src: tuple[int, int], dst: tuple[int, int], *,
              ignore_terrain: bool = False,
              impassable: frozenset | set = frozenset()) -> int | None:
    """Cheapest 8-way movement cost from src to dst, or None if unreachable.
    Entering a cell costs 1, +1 if difficult (unless ignore_terrain).
    Walls and `impassable` cells cannot be crossed (dst itself may be
    impassable-occupied; the caller decides whether ending there is legal)."""
    src, dst = tuple(src), tuple(dst)
    if src == dst:
        return 0
    w, h = enc["grid"]["width"], enc["grid"]["height"]
    walls = cells_of(enc, "wall")
    difficult = set() if ignore_terrain else cells_of(enc, "difficult")
    dist = {src: 0}
    pq = [(0, src)]
    while pq:
        d, cell = heapq.heappop(pq)
        if cell == dst:
            return d
        if d > dist[cell]:
            continue
        x, y = cell
        for nx_ in (x - 1, x, x + 1):
            for ny_ in (y - 1, y, y + 1):
                c = (nx_, ny_)
                if c == cell or not (0 <= nx_ < w and 0 <= ny_ < h):
                    continue
                if c in walls or (c in impassable and c != dst):
                    continue
                nd = d + 1 + (1 if c in difficult else 0)
                if nd < dist.get(c, nd + 1):
                    dist[c] = nd
                    heapq.heappush(pq, (nd, c))
    return None


def cells_of(enc: dict, terrain_type: str) -> set[tuple[int, int]]:
    out = set()
    for feature in enc.get("terrain", []):
        if feature["type"] == terrain_type:
            out.update(tuple(c) for c in feature["cells"])
    return out


def is_dark(enc: dict, cell: tuple[int, int]) -> bool:
    """True in unlit cells: map-wide `dark: true`, or a `dark` terrain cell."""
    return bool(enc.get("dark")) or tuple(cell) in cells_of(enc, "dark")


def blocked(enc: dict, cell: tuple[int, int]) -> str | None:
    x, y = cell
    if not (0 <= x < enc["grid"]["width"] and 0 <= y < enc["grid"]["height"]):
        return "oob"
    if cell in cells_of(enc, "wall"):
        return "wall"
    for cid, pos in enc["positions"].items():
        if tuple(pos) == cell and not enc["monsters"].get(cid, {}).get("dead", False):
            return "occupied"
    return None
