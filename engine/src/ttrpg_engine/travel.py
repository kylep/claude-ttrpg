from pathlib import Path

from ttrpg_engine import clock as clock_mod
from ttrpg_engine import timeline, worldfs
from ttrpg_engine.errors import EngineError


def go(root: Path, dest: str) -> dict:
    if (root / "state" / "encounter.yaml").exists():
        raise EngineError("encounter_active", "cannot travel mid-encounter")
    region = worldfs.read_yaml(root / "canon" / "maps" / "region.yaml")
    party = worldfs.read_yaml(worldfs.state(root, "party"))
    here = party["location"]
    if dest not in region["nodes"]:
        raise EngineError("unknown_node", f"no node {dest}")
    if dest == here:
        raise EngineError("no_route", f"already at {dest}")
    edge = next((e for e in region["edges"] if set(e["between"]) == {here, dest}), None)
    if edge is None:
        raise EngineError("no_route", f"no route {here} -> {dest}")
    clk = clock_mod.advance(worldfs.read_yaml(worldfs.state(root, "clock")), edge["hours"])
    worldfs.write_yaml(worldfs.state(root, "clock"), clk)
    party["location"] = dest
    worldfs.write_yaml(worldfs.state(root, "party"), party)
    timeline.append_event(root, type_="travel",
                          summary=f"party travels {here} -> {dest} ({edge['hours']}h)")
    return {"from": here, "to": dest, "hours": edge["hours"], "clock": clk}
