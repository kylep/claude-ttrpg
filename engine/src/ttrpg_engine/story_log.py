"""The story log: the live viewer's feed as a first-class engine artifact.

`state/story.jsonl` is append-only and engine-written — entries land either as
side effects of engine commands (character created, quest offered, combat
started) or because the GM deliberately posted prose (`engine story narrate`).
The Claude Code transcript is never read; nothing reaches the feed unless it
was written here, so terminal noise is impossible by construction.

Entries carry the game clock and session, never wall time — the story's time
is the world's time, and posts stay deterministic and testable. Markdown is
stored raw and rendered (sanitized) at read time.
"""
import json
import re
from pathlib import Path

from ttrpg_engine import worldfs
from ttrpg_engine.errors import EngineError
from ttrpg_engine.markdown_render import render_markdown

# every type the feed knows how to render; post() rejects anything else so a
# typo'd auto-emit fails loudly at write time, not silently at render time
_TYPES = frozenset({"narration", "scene", "system", "choices", "action",
                    "character", "npc", "monster", "quest", "combat"})


def _path(root: Path) -> Path:
    return root / "state" / "story.jsonl"


def post(root: Path, type_: str, **payload) -> dict:
    """Append one entry to the story log, stamped with the current session and
    game clock. Payload keys are type-specific (md, title, items, ref, ...)."""
    if type_ not in _TYPES:
        raise EngineError("bad_story_type", f"unknown story entry type {type_!r}")
    clk = worldfs.read_yaml(worldfs.state(root, "clock"))
    session = worldfs.read_yaml(worldfs.state(root, "session"))["current"]
    entry = {"session": session,
             "clock": {"date": str(clk["date"]), "hour": clk["hour"]},
             "type": type_, **payload}
    p = _path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def _rendered(rec: dict) -> dict | None:
    """A raw log record shaped for the viewer: markdown rendered to sanitized
    HTML, card types passed through as refs (the client resolves the live
    card via /api/entity). Unknown types are skipped so an older viewer
    degrades gracefully against a newer log."""
    t = rec.get("type")
    out = {"type": t, "session": rec.get("session"), "clock": rec.get("clock")}
    if t in ("narration", "system"):
        out["html"] = render_markdown(str(rec.get("md", "")))
    elif t == "action":
        out["pc"] = rec.get("pc")
        out["name"] = rec.get("name") or rec.get("pc")
        out["html"] = render_markdown(str(rec.get("md", "")))
    elif t == "scene":
        # plain strings — the client inserts them as textContent
        out["title"] = str(rec.get("title", ""))
        out["subtitle"] = str(rec.get("subtitle", ""))
    elif t == "choices":
        out["title"] = str(rec.get("title", ""))
        out["items"] = [render_markdown(str(i)) for i in rec.get("items", [])]
    elif t in ("character", "npc", "monster", "quest"):
        out["ref"] = rec.get("ref")
        out["name"] = rec.get("name")          # display hint if the ref goes stale
        if t == "quest":
            out["event"] = rec.get("event")
    elif t == "combat":
        out["event"] = rec.get("event")
        out["name"] = str(rec.get("name", ""))
        if rec.get("md"):
            out["html"] = render_markdown(str(rec["md"]))
    else:
        return None
    return out


# markdown_render strips script vectors; fenced blocks land as <pre> — the
# player lens drops those wholesale (GM-pasted maps/dumps are never for players)
_PRE_RE = re.compile(r"<pre\b.*?</pre>", re.DOTALL)


def read(root: Path, offset: int = 0, lens: str = "gm") -> tuple[list[dict], int]:
    """Entries past byte `offset`, viewer-ready, plus the next offset. Only
    complete lines are consumed — a partial trailing line stays unread. An
    offset beyond the file (the world was rewound to an earlier save, or a
    new campaign truncated the log) restarts from 0 so the feed self-heals."""
    p = _path(root)
    if not p.exists():
        return [], 0
    try:
        if offset > p.stat().st_size:
            offset = 0
        with p.open("rb") as f:
            f.seek(offset)
            chunk = f.read()
    except OSError:
        return [], offset
    end = chunk.rfind(b"\n")
    if end < 0:
        return [], offset
    chunk = chunk[:end + 1]
    entries = []
    for line in chunk.decode("utf-8", errors="replace").splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if not isinstance(rec, dict):
            continue
        entry = _rendered(rec)
        if entry is None:
            continue
        if lens != "gm" and "html" in entry:
            entry["html"] = _PRE_RE.sub("", entry["html"]).strip()
            if not entry["html"] and entry["type"] in ("narration", "system", "action"):
                continue                     # nothing left once the <pre> went
        entries.append(entry)
    return entries, offset + len(chunk)
