#!/usr/bin/env python3
"""PostToolUse hook: capture engine crashes into the world's feedback.md.

Fires only for Bash tool calls that ran an `engine` command whose output
contains a Python traceback — i.e. a genuine engine bug, not a clean JSON
error envelope (those are usually the rules working as intended; the GM
logs disputed ones by hand per gm.md). No-ops outside a world repo, so it
stays silent during engine development in this repo.

Never blocks: always exits 0.
"""
import datetime
import json
import re
import sys
from pathlib import Path

MARKER = "Traceback (most recent call last)"
TAIL_LINES = 40


def world_root(start: Path) -> Path | None:
    for p in [start, *start.parents]:
        if (p / "world.yaml").exists():
            return p
    return None


def session_number(root: Path) -> str:
    try:
        m = re.search(r"current:\s*(\d+)", (root / "state" / "session.yaml").read_text())
        return m.group(1) if m else "?"
    except OSError:
        return "?"


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    if data.get("tool_name") != "Bash":
        return
    command = (data.get("tool_input") or {}).get("command", "")
    if not re.search(r"(^|[\s/;&|])engine\s", command):
        return
    resp = data.get("tool_response")
    if isinstance(resp, dict):
        output = (resp.get("stderr") or "") + "\n" + (resp.get("stdout") or "")
    else:
        output = str(resp or "")
    if MARKER not in output:
        return
    root = world_root(Path(data.get("cwd") or "."))
    if root is None:
        return
    tail = output.strip().splitlines()[-TAIL_LINES:]
    last_line = tail[-1] if tail else ""
    feedback = root / "feedback.md"
    existing = feedback.read_text() if feedback.exists() else ""
    if command in existing and last_line and last_line in existing:
        return  # same crash already recorded
    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    entry = (
        f"\n## {stamp} — engine crash (auto-captured, session {session_number(root)})\n\n"
        f"Command: `{command}`\n\n"
        "```\n" + "\n".join(tail) + "\n```\n"
    )
    if not existing:
        existing = ("# Feedback\n\nEngine/skill issues hit during play. Crashes are appended\n"
                    "automatically by a hook; the GM adds judgment entries by hand.\n"
                    "Feed these back to the claude-ttrpg repo.\n")
    feedback.write_text(existing + entry)
    print(json.dumps({"systemMessage": f"engine crash captured in {feedback.name}"}))


if __name__ == "__main__":
    main()
