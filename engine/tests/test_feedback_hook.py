"""The engine-feedback PostToolUse hook, run as the harness runs it: JSON on
stdin, appends to the world's feedback.md. Crashes and CLI usage mismatches
are captured; clean JSON error envelopes are not."""
import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "engine-feedback.py"


def run_hook(cwd, command, stdout="", stderr=""):
    payload = {"tool_name": "Bash", "cwd": str(cwd),
               "tool_input": {"command": command},
               "tool_response": {"stdout": stdout, "stderr": stderr}}
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                          capture_output=True, text=True, timeout=10)


def test_usage_error_captured(wroot):
    res = run_hook(wroot, "engine gold spend --amount 1 --reason x",
                   stderr="Usage: engine gold spend [OPTIONS]\n"
                          "Error: No such option: --reason (Possible options: --amount)")
    assert res.returncode == 0
    assert "CLI mismatch" in res.stdout
    text = (wroot / "feedback.md").read_text()
    assert "engine CLI mismatch" in text
    assert "No such option: --reason" in text


def test_traceback_captured(wroot):
    run_hook(wroot, "engine attack --attacker x --target y",
             stderr="Traceback (most recent call last):\n  File ...\nKeyError: 'hp'")
    text = (wroot / "feedback.md").read_text()
    assert "engine crash" in text and "KeyError: 'hp'" in text


def test_clean_json_error_ignored(wroot):
    res = run_hook(wroot, "engine gold spend --amount 999 --actor pc-x",
                   stdout='{"error": {"code": "not_enough", "message": "only 3 gp"}}')
    assert res.stdout.strip() == ""
    assert not (wroot / "feedback.md").exists()


def test_non_engine_command_ignored(wroot):
    run_hook(wroot, "git commit -m x", stderr="Error: No such option: --frobnicate")
    assert not (wroot / "feedback.md").exists()


def test_duplicate_not_recorded_twice(wroot):
    for _ in range(2):
        run_hook(wroot, "engine gold spend --reason x",
                 stderr="Error: No such option: --reason (Possible options: --amount)")
    assert (wroot / "feedback.md").read_text().count("CLI mismatch") == 1


def test_outside_world_noop(tmp_path):
    res = run_hook(tmp_path, "engine gold spend --reason x",
                   stderr="Error: No such option: --reason")
    assert res.returncode == 0
    assert not (tmp_path / "feedback.md").exists()