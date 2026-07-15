import json
import os
import re
from pathlib import Path

from ttrpg_engine import story


def sanitized(world: Path) -> str:
    return re.sub(r"[^A-Za-z0-9-]", "-", str(world.resolve()))


def user(text, world, **over):
    rec = {"type": "user", "cwd": str(world.resolve()),
           "message": {"role": "user", "content": text}}
    rec.update(over)
    return json.dumps(rec)


def gm(parts, world, **over):
    if isinstance(parts, str):
        parts = [{"type": "text", "text": parts}]
    rec = {"type": "assistant", "cwd": str(world.resolve()),
           "message": {"role": "assistant", "content": parts}}
    rec.update(over)
    return json.dumps(rec)


def write_transcript(base, world, lines, name="s1.jsonl", dirname=None, mtime=None):
    d = base / (dirname or sanitized(world))
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_text("".join(line + "\n" for line in lines))
    if mtime is not None:
        os.utime(p, (mtime, mtime))
    return p


def make_world(tmp_path):
    world = tmp_path / "my world!"
    world.mkdir()
    base = tmp_path / "projects"
    base.mkdir()
    return world, base


# ---------------------------------------------------------------------------
# project dir discovery
# ---------------------------------------------------------------------------

def test_project_dir_sanitized_mapping(tmp_path):
    world, base = make_world(tmp_path)
    assert "-" in sanitized(world) and " " not in sanitized(world)
    write_transcript(base, world, [user("hi", world)])
    d = story.project_dir_for(world, base)
    assert d == base / sanitized(world)


def test_project_dir_scan_fallback(tmp_path):
    world, base = make_world(tmp_path)
    other = tmp_path / "otherworld"
    other.mkdir()
    # sanitized-named dir exists but its transcript belongs to another cwd
    write_transcript(base, other, [user("hi", other)], dirname=sanitized(world))
    match = write_transcript(base, world, [user("hi", world)], dirname="renamed-dir")
    assert story.project_dir_for(world, base) == match.parent


def test_project_dir_missing(tmp_path):
    world, base = make_world(tmp_path)
    assert story.project_dir_for(world, base) is None
    assert story.latest_transcript(world, base) is None
    assert story.read_story(world, None, base) == ([], {"file": None, "offset": 0})


def test_latest_transcript_by_mtime(tmp_path):
    world, base = make_world(tmp_path)
    write_transcript(base, world, [user("old", world)], name="a.jsonl", mtime=1000)
    newest = write_transcript(base, world, [user("new", world)], name="b.jsonl", mtime=2000)
    assert story.latest_transcript(world, base) == newest


# ---------------------------------------------------------------------------
# entry extraction
# ---------------------------------------------------------------------------

def test_operator_and_gm_entries_in_order(tmp_path):
    world, base = make_world(tmp_path)
    write_transcript(base, world, [
        user("I open the **door**", world),
        gm("The door *creaks* open.", world),
        user("I step inside", world),
        gm("Darkness swallows you.", world),
    ])
    entries, cursor = story.read_story(world, None, base)
    assert [e["role"] for e in entries] == ["operator", "gm", "operator", "gm"]
    assert "<strong>door</strong>" in entries[0]["html"]
    assert "<em>creaks</em>" in entries[1]["html"]
    assert cursor["file"] == "s1.jsonl" and cursor["offset"] > 0


def test_noise_skipped(tmp_path):
    world, base = make_world(tmp_path)
    write_transcript(base, world, [
        gm([{"type": "tool_use", "id": "t1", "name": "Bash", "input": {}}], world),
        user([{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}], world),
        user("meta note", world, isMeta=True),
        gm("sidechain text", world, isSidechain=True),
        user("<command-name>/clear</command-name>", world),
        user("<local-command-stdout>out</local-command-stdout>", world),
        user("<local-command-caveat>caveat</local-command-caveat>", world),
        user("<system-reminder>only a\nreminder</system-reminder>", world),
        user("[Request interrupted by user]", world),
        gm("API Error: overloaded", world),
        gm("Failed to authenticate.", world),
        json.dumps({"type": "queue-operation", "operation": "enqueue"}),
        json.dumps({"type": "attachment", "cwd": str(world.resolve())}),
        user("real line <system-reminder>secret\nstuff</system-reminder> here", world),
        gm([{"type": "thinking", "thinking": "hmm"},
            {"type": "text", "text": "The goblin snarls."}], world),
    ])
    entries, _ = story.read_story(world, None, base)
    assert [e["role"] for e in entries] == ["operator", "gm"]
    assert "real line" in entries[0]["html"] and "here" in entries[0]["html"]
    assert "secret" not in entries[0]["html"]
    assert "goblin snarls" in entries[1]["html"]
    assert "hmm" not in entries[1]["html"]


def test_script_stripped_from_malicious_entry(tmp_path):
    world, base = make_world(tmp_path)
    write_transcript(base, world, [
        gm("Look out! <script>alert(1)</script> A trap!", world),
    ])
    entries, _ = story.read_story(world, None, base)
    assert len(entries) == 1
    assert "<script" not in entries[0]["html"]
    assert "alert(1)" not in entries[0]["html"]
    assert "A trap!" in entries[0]["html"]


def test_malformed_json_line_skipped(tmp_path):
    world, base = make_world(tmp_path)
    write_transcript(base, world, [
        user("before", world),
        "{this is not json",
        gm("after", world),
    ])
    entries, _ = story.read_story(world, None, base)
    assert [e["role"] for e in entries] == ["operator", "gm"]


# ---------------------------------------------------------------------------
# cursor behavior
# ---------------------------------------------------------------------------

def test_incremental_cursor(tmp_path):
    world, base = make_world(tmp_path)
    p = write_transcript(base, world, [user("first", world)])
    entries, cursor = story.read_story(world, None, base)
    assert len(entries) == 1 and cursor["offset"] == p.stat().st_size

    with p.open("a") as f:
        f.write(gm("second", world) + "\n")
    entries, cursor2 = story.read_story(world, cursor, base)
    assert [e["role"] for e in entries] == ["gm"]
    assert cursor2["offset"] > cursor["offset"] == cursor2["offset"] - len(gm("second", world) + "\n")

    entries, cursor3 = story.read_story(world, cursor2, base)
    assert entries == [] and cursor3 == cursor2


def test_partial_line_not_consumed(tmp_path):
    world, base = make_world(tmp_path)
    p = write_transcript(base, world, [user("first", world)])
    _, cursor = story.read_story(world, None, base)
    half = user("later", world)
    with p.open("a") as f:
        f.write(half[:10])
    entries, cursor2 = story.read_story(world, cursor, base)
    assert entries == [] and cursor2 == cursor
    with p.open("a") as f:
        f.write(half[10:] + "\n")
    entries, _ = story.read_story(world, cursor2, base)
    assert len(entries) == 1 and "later" in entries[0]["html"]


def test_newer_session_file_resets_cursor(tmp_path):
    world, base = make_world(tmp_path)
    write_transcript(base, world, [user("old session", world)], name="a.jsonl", mtime=1000)
    _, cursor = story.read_story(world, None, base)
    assert cursor["file"] == "a.jsonl"

    p2 = write_transcript(base, world, [gm("new session", world)], name="b.jsonl", mtime=2000)
    entries, cursor2 = story.read_story(world, cursor, base)
    assert [e["role"] for e in entries] == ["gm"]
    assert "new session" in entries[0]["html"]
    assert cursor2 == {"file": "b.jsonl", "offset": p2.stat().st_size}


# --- viewer-review regression fixes -----------------------------------------

def _write_session(base, world, name, records):
    import json as _json
    pdir = base / "proj"
    pdir.mkdir(exist_ok=True)
    f = pdir / name
    f.write_text("".join(_json.dumps(r) + "\n" for r in records))
    return f


def _rec(role, text):
    return {"type": role, "cwd": None, "message": {"role": role, "content": text}}


def test_player_lens_strips_fenced_code_blocks(tmp_path, monkeypatch):
    from ttrpg_engine import story
    world = tmp_path / "w"; world.mkdir()
    monkeypatch.setattr(story, "project_dir_for", lambda *a, **k: tmp_path / "proj")
    _write_session(tmp_path, world, "s.jsonl", [
        _rec("assistant", "The goblin lunges.\n\n```\n0 1 2\ng . .\n```\n\nWhat do you do?"),
    ])
    gm, _ = story.read_story(world, None, lens="gm")
    assert any("<pre>" in e["html"] for e in gm)              # GM keeps the map
    player, _ = story.read_story(world, None, lens="player")
    assert player and all("<pre>" not in e["html"] for e in player)
    assert "goblin lunges" in player[0]["html"]              # prose survives


def test_player_lens_drops_map_only_entries(tmp_path, monkeypatch):
    from ttrpg_engine import story
    world = tmp_path / "w"; world.mkdir()
    monkeypatch.setattr(story, "project_dir_for", lambda *a, **k: tmp_path / "proj")
    _write_session(tmp_path, world, "s.jsonl", [
        _rec("assistant", "```\nmap only, no prose\n```"),
        _rec("user", "i attack"),
    ])
    player, _ = story.read_story(world, None, lens="player")
    roles = [e["role"] for e in player]
    assert roles == ["operator"]                             # the map-only beat is gone


def test_transcript_sticky_ignores_concurrent_newer_session(tmp_path, monkeypatch):
    import os, time
    from ttrpg_engine import story
    world = tmp_path / "w"; world.mkdir()
    monkeypatch.setattr(story, "project_dir_for", lambda *a, **k: tmp_path / "proj")
    a = _write_session(tmp_path, world, "a.jsonl", [_rec("assistant", "session A beat")])
    entries, cursor = story.read_story(world, None, lens="gm")
    assert cursor["file"] == "a.jsonl" and "session A" in entries[0]["html"]
    # a second concurrent session writes a newer file
    b = _write_session(tmp_path, world, "b.jsonl", [_rec("assistant", "session B beat")])
    now = time.time()
    os.utime(a, (now, now)); os.utime(b, (now + 1, now + 1))  # both fresh, b barely newer
    entries, cursor2 = story.read_story(world, cursor, lens="gm")
    assert cursor2["file"] == "a.jsonl"                      # stayed on A, no flap
    # A goes quiet, B keeps going -> real handoff
    os.utime(a, (now - 999, now - 999))
    entries, cursor3 = story.read_story(world, cursor2, lens="gm")
    assert cursor3["file"] == "b.jsonl" and "session B" in entries[0]["html"]
