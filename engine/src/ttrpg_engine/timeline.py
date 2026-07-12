from pathlib import Path

from ttrpg_engine import worldfs


def events_for_date(root: Path, date: str) -> list[Path]:
    return sorted((root / "timeline").glob(f"{date}-*.yaml"))


def append_event(root: Path, *, type_: str, summary: str,
                 actors: list[str] | None = None, delta: dict | None = None,
                 override: bool = False) -> str:
    clk = worldfs.read_yaml(worldfs.state(root, "clock"))
    session = worldfs.read_yaml(worldfs.state(root, "session"))["current"]
    date = str(clk["date"])
    existing = events_for_date(root, date)
    seq = 1 + max((int(p.stem.rsplit("-", 1)[1]) for p in existing), default=0)
    event_id = f"{date}-{seq:03d}"
    worldfs.write_yaml(root / "timeline" / f"{event_id}.yaml", {
        "id": event_id, "session": session, "type": type_,
        "date": date, "hour": clk["hour"],
        "actors": actors or [], "summary": summary,
        "delta": delta or {}, "override": override,
    })
    return event_id
