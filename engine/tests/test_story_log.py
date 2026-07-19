import json

import pytest
from typer.testing import CliRunner

from ttrpg_engine import story_log, worldfs
from ttrpg_engine.cli import app
from ttrpg_engine.errors import EngineError
from conftest import make_pc

runner = CliRunner()


def _raw(wroot):
    p = wroot / "state" / "story.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []


# ---------------------------------------------------------------------------
# core post/read
# ---------------------------------------------------------------------------

def test_post_stamps_session_and_clock(wroot):
    entry = story_log.post(wroot, "narration", md="Dawn breaks.")
    assert entry["session"] == 0 and entry["clock"] == {"date": "1203-04-17", "hour": 9}
    entries, offset = story_log.read(wroot)
    assert entries[0]["type"] == "narration"
    assert "<p>Dawn breaks.</p>" == entries[0]["html"]
    assert offset > 0


def test_post_rejects_unknown_type(wroot):
    with pytest.raises(EngineError) as e:
        story_log.post(wroot, "tweet", md="no")
    assert e.value.code == "bad_story_type"


def test_read_is_incremental_and_rewind_safe(wroot):
    story_log.post(wroot, "narration", md="one")
    _, offset = story_log.read(wroot)
    story_log.post(wroot, "narration", md="two")
    entries, offset2 = story_log.read(wroot, offset)
    assert [e["html"] for e in entries] == ["<p>two</p>"]
    # a rewound world (file shrank under the cursor) restarts from the top
    entries, offset3 = story_log.read(wroot, offset2 + 10_000)
    assert len(entries) == 2 and offset3 == offset2


def test_player_lens_strips_fenced_blocks(wroot):
    story_log.post(wroot, "narration", md="Before\n```\nsecret map\n```\nAfter")
    story_log.post(wroot, "narration", md="```\nonly a map\n```")
    gm_entries, _ = story_log.read(wroot, lens="gm")
    assert "secret map" in gm_entries[0]["html"]
    player, _ = story_log.read(wroot, lens="player")
    assert len(player) == 1                       # map-only beat dropped entirely
    assert "secret map" not in player[0]["html"]
    assert "Before" in player[0]["html"] and "After" in player[0]["html"]


def test_unknown_entry_type_skipped_on_read(wroot):
    (wroot / "state" / "story.jsonl").write_text(
        '{"type": "hologram", "md": "future"}\n'
        '{"type": "narration", "md": "still works"}\n')
    entries, _ = story_log.read(wroot)
    assert [e["type"] for e in entries] == ["narration"]


def test_malicious_markdown_sanitized(wroot):
    story_log.post(wroot, "narration", md="Look <script>alert(1)</script> out")
    entries, _ = story_log.read(wroot)
    assert "<script" not in entries[0]["html"]


# ---------------------------------------------------------------------------
# CLI posting commands
# ---------------------------------------------------------------------------

def test_cli_story_commands(wroot):
    make_pc()
    for args in (["story", "scene", "--title", "Thornbury", "--subtitle", "dawn"],
                 ["story", "narrate", "--text", "The **rain** quits."],
                 ["story", "choices", "--item", "Talk to Halda", "--item", "Check the board"],
                 ["story", "action", "--pc", "pc-borin", "--text", "I kick the door."]):
        res = runner.invoke(app, args)
        assert res.exit_code == 0, res.stdout
    entries, _ = story_log.read(wroot)
    types = [e["type"] for e in entries]
    assert types == ["character", "scene", "narration", "choices", "action"]
    assert entries[1]["title"] == "Thornbury"
    assert entries[3]["items"] == ["<p>Talk to Halda</p>", "<p>Check the board</p>"]
    assert entries[4]["name"] == "Borin"          # action attributed by display name


def test_cli_story_narrate_stdin(wroot):
    res = runner.invoke(app, ["story", "narrate", "--text", "-"],
                        input="A long beat\nover two lines.\n")
    assert res.exit_code == 0, res.stdout
    entries, _ = story_log.read(wroot)
    assert "two lines" in entries[-1]["html"]


def test_cli_story_reveal_validates_refs(wroot):
    make_pc()
    res = runner.invoke(app, ["story", "reveal", "--pc", "pc-borin"])
    assert res.exit_code == 0, res.stdout
    assert json.loads(res.stdout)["type"] == "character"
    res = runner.invoke(app, ["story", "reveal", "--monster", "goblin"])
    assert res.exit_code == 0, res.stdout
    res = runner.invoke(app, ["story", "reveal", "--monster", "dragon"])
    assert res.exit_code == 1
    res = runner.invoke(app, ["story", "reveal"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["error"]["code"] == "bad_reveal"


# ---------------------------------------------------------------------------
# auto-emits: the engine writes the structured beats itself
# ---------------------------------------------------------------------------

def test_auto_emits_across_a_session(wroot):
    res = runner.invoke(app, ["session", "start"])
    assert res.exit_code == 0
    make_pc()
    res = runner.invoke(app, ["quest", "offer", "--title", "Rats", "--desc", "Rats.",
                              "--giver", "world", "--gold", "5", "--spawn"])
    assert res.exit_code == 0, res.stdout
    res = runner.invoke(app, ["quest", "accept", "rats", "--pcs", "pc-borin"])
    assert res.exit_code == 0, res.stdout
    res = runner.invoke(app, ["--seed", "5", "encounter", "start",
                              "maps/encounters/skirmish.yaml"])
    assert res.exit_code == 0, res.stdout
    res = runner.invoke(app, ["--seed", "5", "encounter", "end"])
    assert res.exit_code == 0, res.stdout
    res = runner.invoke(app, ["quest", "complete", "rats", "--to", "pc-borin"])
    assert res.exit_code == 0, res.stdout
    res = runner.invoke(app, ["travel", "--to", "cave"])
    assert res.exit_code == 0, res.stdout

    raw = _raw(wroot)
    got = [(r["type"], r.get("event")) for r in raw]
    assert got == [
        ("system", None),            # Session 1 begins
        ("character", None),         # Borin joins
        ("quest", "offered"),
        ("quest", "accepted"),
        ("combat", "start"),
        ("combat", "end"),
        ("quest", "completed"),
        ("system", None),            # arrival line
    ]
    assert raw[0]["md"] == "**Session 1** begins."
    assert "arrives at" in raw[-1]["md"]
    end = next(r for r in raw if r.get("event") == "end")
    assert "xp each" in end["md"]


# ---------------------------------------------------------------------------
# roll beats (feature A): transparency, with a GM-only lens filter
# ---------------------------------------------------------------------------

def test_post_roll_and_gm_only_filter(wroot):
    story_log.post_roll(wroot, actor="Kyle", label="Perception", expr="d20+2",
                        total=16, outcome="success", target_num=13,
                        target_kind="DC", gm_only=False)
    story_log.post_roll(wroot, actor="Goblin 1", label="Attack vs pc-borin",
                        expr="d20+4", total=18, outcome="hit", target_num=15,
                        target_kind="AC", gm_only=True)
    gm = [e for e in story_log.read(wroot, lens="gm")[0] if e["type"] == "roll"]
    assert len(gm) == 2
    assert gm[0]["actor"] == "Kyle" and gm[0]["expr"] == "d20+2"
    assert gm[0]["total"] == 16 and gm[0]["target_num"] == 13
    assert gm[0]["target_kind"] == "DC" and gm[0]["outcome"] == "success"
    # a hidden foe's roll must never reach the player feed
    player = [e for e in story_log.read(wroot, lens="player")[0] if e["type"] == "roll"]
    assert len(player) == 1 and player[0]["actor"] == "Kyle"


def test_cli_check_posts_player_visible_roll(wroot):
    make_pc()
    res = runner.invoke(app, ["check", "--actor", "pc-borin", "--attr", "WIS",
                              "--dc", "10", "--skill", "perception"])
    assert res.exit_code == 0, res.stdout
    rolls = [e for e in story_log.read(wroot, lens="player")[0] if e["type"] == "roll"]
    assert len(rolls) == 1
    r = rolls[0]
    assert r["actor"] == "Borin"                 # display name, not the id
    assert r["label"] == "Perception"
    assert r["expr"].startswith("d20") and r["target_kind"] == "DC"
    assert r["outcome"] in ("success", "fail")