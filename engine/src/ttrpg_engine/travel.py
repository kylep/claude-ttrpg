from pathlib import Path

from ttrpg_engine import clock as clock_mod
from ttrpg_engine import timeline, worldfs
from ttrpg_engine.errors import EngineError


def go(root: Path, dest: str, pcs: list[str] | None = None) -> dict:
    if (root / "state" / "encounter.yaml").exists():
        raise EngineError("encounter_active", "cannot travel mid-encounter")
    region = worldfs.read_yaml(root / "canon" / "maps" / "region.yaml")
    party = worldfs.read_yaml(worldfs.state(root, "party"))
    if dest not in region["nodes"]:
        raise EngineError("unknown_node", f"no node {dest}")

    if pcs is None:
        movers = list(party["members"])
        here = party["location"]
    else:
        movers = pcs
        sheets = {}
        for pid in movers:
            if pid not in party["members"]:
                raise EngineError("not_found", f"no such PC {pid}")
            sheet = worldfs.read_yaml(worldfs.state(root, f"party/{pid}"))
            if "dead" in {e["name"] for e in sheet["effects"]}:
                raise EngineError("dead", f"{pid} is dead and cannot travel")
            sheets[pid] = sheet
        here = worldfs.pc_location(sheets[movers[0]], party)
        for pid in movers[1:]:
            loc = worldfs.pc_location(sheets[pid], party)
            if loc != here:
                raise EngineError("split_party", f"{pid} is at {loc}, not {here}")

    if dest == here:
        raise EngineError("no_route", f"already at {dest}")
    edge = next((e for e in region["edges"] if set(e["between"]) == {here, dest}), None)
    if edge is None:
        raise EngineError("no_route", f"no route {here} -> {dest}")

    clk = clock_mod.advance(worldfs.read_yaml(worldfs.state(root, "clock")), edge["hours"])
    worldfs.write_yaml(worldfs.state(root, "clock"), clk)

    if pcs is None:
        party["location"] = dest
        worldfs.write_yaml(worldfs.state(root, "party"), party)
        for pid in movers:
            sheet = worldfs.read_yaml(worldfs.state(root, f"party/{pid}"))
            sheet["location"] = dest
            worldfs.write_yaml(worldfs.state(root, f"party/{pid}"), sheet)
        summary = f"party travels {here} -> {dest} ({edge['hours']}h)"
    else:
        for pid in movers:
            sheets[pid]["location"] = dest
            worldfs.write_yaml(worldfs.state(root, f"party/{pid}"), sheets[pid])
        summary = (f"{', '.join(movers)} travel {here} -> {dest} ({edge['hours']}h); "
                   "rest of the party stays behind")

    timeline.append_event(root, type_="travel", actors=movers, summary=summary)
    return {"from": here, "to": dest, "hours": edge["hours"], "clock": clk, "pcs": movers}
