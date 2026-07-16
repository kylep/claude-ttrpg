#!/usr/bin/env python3
"""PostToolUse hook: capture engine problems into the world's feedback.md.

Fires only for Bash tool calls that ran an `engine` command and captures
two classes of output:

- **Crashes** — a Python traceback: a genuine engine bug.
- **CLI mismatches** — a usage error ("No such option", "No such command",
  "Missing option", unexpected argument): the GM reached for a flag or
  command it expected to exist. That expectation is premium feedback — it
  says what the CLI's surface is missing — and the GM usually just retries
  and moves on without logging it.

Clean JSON error envelopes are neither (the rules working as intended; the
GM logs disputed ones by hand per gm.md). No-ops outside a world repo, so
it stays silent during engine development in this repo.

Never blocks: always exits 0.
"""
import datetime
import json
import re
import sys
from pathlib import Path

MARKER = "Traceback (most recent call last)"
# typer/click usage-error phrasings — the GM asked the CLI for something it
# doesn't have
USAGE_RE = re.compile(r"No such option|No such command|Missing option"
                      r"|Got unexpected extra argument")
TAIL_LINES = 40
USAGE_TAIL_LINES = 8   # usage errors are short; keep the entry tight


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
    if MARKER in output:
        kind, tail_n = "engine crash", TAIL_LINES
    elif USAGE_RE.search(output):
        kind, tail_n = "engine CLI mismatch", USAGE_TAIL_LINES
    else:
        return
    root = world_root(Path(data.get("cwd") or "."))
    if root is None:
        return
    tail = output.strip().splitlines()[-tail_n:]
    last_line = tail[-1] if tail else ""
    feedback = root / "feedback.md"
    existing = feedback.read_text() if feedback.exists() else ""
    if command in existing and last_line and last_line in existing:
        return  # same problem already recorded
    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    entry = (
        f"\n## {stamp} — {kind} (auto-captured, session {session_number(root)})\n\n"
        f"Command: `{command}`\n\n"
        "```\n" + "\n".join(tail) + "\n```\n"
    )
    if not existing:
        existing = ("# Feedback\n\nEngine/skill issues hit during play. Crashes are appended\n"
                    "automatically by a hook; the GM adds judgment entries by hand.\n"
                    "Feed these back to the claude-ttrpg repo.\n")
    feedback.write_text(existing + entry)
    print(json.dumps({"systemMessage": f"{kind} captured in {feedback.name}"}))


if __name__ == "__main__":
    main()
