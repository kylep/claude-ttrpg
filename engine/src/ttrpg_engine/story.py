"""Narration feed for the live viewer: tails Claude Code session transcripts
(JSONL under ~/.claude/projects/) for the world's cwd. Strictly read-only and
never fatal — anything unrecognized is skipped so the story pane degrades
gracefully instead of taking the viewer down with a log-format change."""

import json
import re
from pathlib import Path

from ttrpg_engine import export

_SYSTEM_REMINDER_RE = re.compile(r"<system-reminder>.*?</system-reminder>", re.DOTALL)
_SKIP_MARKERS = ("<command-name>", "<local-command-stdout>", "<local-command-caveat>")
_PRE_RE = re.compile(r"<pre\b.*?</pre>", re.DOTALL)
# a session the viewer is already following must go quiet this long before the
# feed jumps to a genuinely newer transcript — stops two concurrent sessions in
# the same world dir from flapping the feed back and forth
_STICKY_SECONDS = 15


def _newest_jsonl(project_dir: Path) -> Path | None:
    try:
        files = list(project_dir.glob("*.jsonl"))
        return max(files, key=lambda p: p.stat().st_mtime) if files else None
    except OSError:
        return None


def _transcript_cwd_matches(project_dir: Path, cwd: str) -> bool:
    newest = _newest_jsonl(project_dir)
    if newest is None:
        return False
    # only the head of the file: enough to find a cwd-carrying record without
    # scanning a whole session log
    carrying = 0
    try:
        with newest.open(encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                if i >= 50 or carrying >= 5:
                    break
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(rec, dict) or "cwd" not in rec:
                    continue
                if rec["cwd"] == cwd:
                    return True
                carrying += 1
    except OSError:
        return False
    return False


def project_dir_for(world_root: Path, projects_base: Path | None = None) -> Path | None:
    base = projects_base if projects_base is not None else Path.home() / ".claude" / "projects"
    cwd = str(Path(world_root).resolve())
    primary = base / re.sub(r"[^A-Za-z0-9-]", "-", cwd)
    if primary.is_dir() and _transcript_cwd_matches(primary, cwd):
        return primary
    if not base.is_dir():
        return None
    for d in sorted(base.iterdir()):
        if d.is_dir() and d != primary and _transcript_cwd_matches(d, cwd):
            return d
    return None


def latest_transcript(world_root: Path, projects_base: Path | None = None) -> Path | None:
    project_dir = project_dir_for(world_root, projects_base)
    return _newest_jsonl(project_dir) if project_dir is not None else None


def _joined_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(p["text"] for p in content
                         if isinstance(p, dict) and p.get("type") == "text"
                         and isinstance(p.get("text"), str))
    return ""


def _entry_for(rec: dict) -> dict | None:
    if rec.get("isSidechain") or rec.get("isMeta"):
        return None
    msg = rec.get("message")
    if rec.get("type") not in ("user", "assistant") or not isinstance(msg, dict):
        return None
    text = _joined_text(msg.get("content"))
    if rec["type"] == "user":
        text = _SYSTEM_REMINDER_RE.sub("", text)
        if any(marker in text for marker in _SKIP_MARKERS):
            return None
        text = text.strip()
        if not text or text.startswith("[Request interrupted"):
            return None
        role = "operator"
    else:
        text = text.strip()
        if not text or text.startswith("API Error") or text.startswith("Failed to authenticate"):
            return None
        role = "gm"
    return {"role": role, "html": export._md(text)}


def _select_transcript(project_dir: Path, cursor: dict | None) -> Path | None:
    """The transcript to read: normally the newest, but stick with the one the
    client is already following (its cursor file) unless that session has gone
    quiet and a genuinely newer one has taken over."""
    newest = _newest_jsonl(project_dir)
    if newest is None or not cursor or not cursor.get("file"):
        return newest
    current = project_dir / cursor["file"]
    if current == newest or not current.is_file():
        return newest
    try:
        if newest.stat().st_mtime - current.stat().st_mtime <= _STICKY_SECONDS:
            return current  # both recently written — don't flap the feed
    except OSError:
        pass
    return newest


def _apply_lens(entries: list[dict], lens: str) -> list[dict]:
    """Player lens strips fenced code blocks — ASCII battle maps (which show
    hidden monsters and true positions) and raw command/JSON dumps the GM
    pastes into narration are always fenced, never player-facing prose."""
    if lens == "gm":
        return entries
    out = []
    for e in entries:
        html = _PRE_RE.sub("", e["html"]).strip()
        if html:
            out.append({"role": e["role"], "html": html})
    return out


def read_story(world_root: Path, cursor: dict | None,
               projects_base: Path | None = None,
               lens: str = "gm") -> tuple[list[dict], dict]:
    project_dir = project_dir_for(world_root, projects_base)
    transcript = _select_transcript(project_dir, cursor) if project_dir else None
    if transcript is None:
        return [], {"file": None, "offset": 0}
    offset = 0
    if cursor and cursor.get("file") == transcript.name:
        offset = cursor.get("offset", 0)
    try:
        with transcript.open("rb") as f:
            f.seek(offset)
            chunk = f.read()
    except OSError:
        return [], {"file": transcript.name, "offset": offset}
    end = chunk.rfind(b"\n")  # only complete lines; a partial tail stays unconsumed
    if end < 0:
        return [], {"file": transcript.name, "offset": offset}
    chunk = chunk[:end + 1]
    entries = []
    for line in chunk.decode("utf-8", errors="replace").splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict):
            entry = _entry_for(rec)
            if entry is not None:
                entries.append(entry)
    return _apply_lens(entries, lens), {"file": transcript.name, "offset": offset + len(chunk)}
