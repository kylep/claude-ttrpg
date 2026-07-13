from pathlib import Path

from ttrpg_engine import timeline, worldfs
from ttrpg_engine.errors import EngineError


def _sheet(root: Path, actor: str) -> dict:
    return worldfs.read_yaml(worldfs.state(root, f"party/{actor}"))


def add_item(root: Path, g: dict, actor: str, item: str, qty: int) -> dict:
    if item not in g["items"]:
        raise EngineError("unknown_item", f"no item {item} in this game")
    sheet = _sheet(root, actor)
    line = next((l for l in sheet["inventory"] if l["item"] == item), None)
    if line:
        line["qty"] += qty
    else:
        sheet["inventory"].append({"item": item, "qty": qty})
    worldfs.write_yaml(worldfs.state(root, f"party/{actor}"), sheet)
    timeline.append_event(root, type_="item", actors=[actor],
                          summary=f"{actor} gains {qty}x {item}")
    return {"actor": actor, "inventory": sheet["inventory"]}


def remove_item(root: Path, g: dict, actor: str, item: str, qty: int) -> dict:
    sheet = _sheet(root, actor)
    line = next((l for l in sheet["inventory"] if l["item"] == item), None)
    if line is None or line["qty"] < qty:
        raise EngineError("not_enough", f"{actor} does not have {qty}x {item}")
    line["qty"] -= qty
    sheet["inventory"] = [l for l in sheet["inventory"] if l["qty"] > 0]
    worldfs.write_yaml(worldfs.state(root, f"party/{actor}"), sheet)
    timeline.append_event(root, type_="item", actors=[actor],
                          summary=f"{actor} loses {qty}x {item}")
    return {"actor": actor, "inventory": sheet["inventory"]}


def adjust_gold(root: Path, target: str, amount: int) -> dict:
    if target == "party":
        data = worldfs.read_yaml(worldfs.state(root, "party"))
    else:
        data = _sheet(root, target)
    if data["gold"] + amount < 0:
        raise EngineError("not_enough", f"{target} has only {data['gold']} gp")
    before = data["gold"]
    data["gold"] += amount
    path = worldfs.state(root, "party" if target == "party" else f"party/{target}")
    worldfs.write_yaml(path, data)
    verb = "gains" if amount >= 0 else "spends"
    timeline.append_event(root, type_="gold", actors=[] if target == "party" else [target],
                          summary=f"{target} {verb} {abs(amount)} gp",
                          delta={target: {"gold": [before, data["gold"]]}})
    return {"target": target, "gold": data["gold"]}
