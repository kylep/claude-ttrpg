def chebyshev(a: tuple[int, int], b: tuple[int, int]) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def cells_of(enc: dict, terrain_type: str) -> set[tuple[int, int]]:
    out = set()
    for feature in enc.get("terrain", []):
        if feature["type"] == terrain_type:
            out.update(tuple(c) for c in feature["cells"])
    return out


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
