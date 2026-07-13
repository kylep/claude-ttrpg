import json
import shutil
from pathlib import Path

from typer.testing import CliRunner

from ttrpg_engine.cli import app

FIXTURE_GAME = Path(__file__).parent / "fixtures" / "minigame"

runner = CliRunner()


def _export(*args):
    return runner.invoke(app, ["export", *args])


def _no_external_refs(html: str) -> bool:
    return "<link" not in html and "<script src" not in html


# --- export game ------------------------------------------------------------


def test_export_game_inside_world(wroot):
    res = _export("game")
    assert res.exit_code == 0, res.stdout
    payload = json.loads(res.stdout)
    out = Path(payload["file"])
    assert out == wroot / "exports" / "claude-ttrpg-game-handbook.html"
    assert out.exists()
    assert payload["sections"] > 0

    html = out.read_text()
    assert _no_external_refs(html)
    assert "fighter" in html.lower()          # class name
    assert "cleric" in html.lower()
    assert "second_wind" in html.lower() or "Second Wind" in html  # feature tag
    assert "sacred_flame" in html.lower() or "Sacred Flame" in html  # spell card
    assert "Goblin" in html and "ac" in html.lower()  # bestiary stat block header + field
    assert "13" in html  # goblin ac value present somewhere in the stat block
    assert "torch" in html.lower()  # item grouped by type


def test_export_game_repo_side_with_game_flag(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # nowhere near a world.yaml
    res = _export("game", "--game", str(FIXTURE_GAME), "--out", str(tmp_path / "out"))
    assert res.exit_code == 0, res.stdout
    payload = json.loads(res.stdout)
    out = Path(payload["file"])
    assert out == tmp_path / "out" / "claude-ttrpg-game-handbook.html"
    assert out.exists()
    assert "fighter" in out.read_text().lower()


def test_export_game_no_world_no_game_flag_errors(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    res = _export("game")
    payload = json.loads(res.stdout)
    assert payload["error"]["code"] == "no_world"


def test_export_game_core_rules_generated_from_yaml(wroot):
    res = _export("game")
    html = Path(json.loads(res.stdout)["file"]).read_text()
    # standard array values from ruleset/core.yaml, not hardcoded text
    for value in ["15", "14", "13", "12", "10", "8"]:
        assert value in html
    # DCs from ruleset/core.yaml
    assert "10" in html and "16" in html


# --- export world ------------------------------------------------------------


def test_export_world_inside_world(wroot):
    res = _export("world")
    assert res.exit_code == 0, res.stdout
    payload = json.loads(res.stdout)
    out = Path(payload["file"])
    assert out == wroot / "exports" / "claude-ttrpg-world-guide.html"
    assert out.exists()

    html = out.read_text()
    assert _no_external_refs(html)
    assert "Sunbleached Hills" in html          # setting.md phrase, rendered from markdown
    assert "goblin-infested cave" in html       # history.md phrase
    assert "Town Watch" in html                 # faction
    assert "The Mayor" in html                  # npc
    assert "town" in html.lower() and "cave" in html.lower()  # region map nodes
    assert "4" in html                          # travel hours town->cave


def test_export_world_repo_side(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    res = _export("world", "--game", str(FIXTURE_GAME), "--out", str(tmp_path / "out"))
    assert res.exit_code == 0, res.stdout
    html = Path(json.loads(res.stdout)["file"]).read_text()
    assert "Sunbleached Hills" in html
    assert "Town Watch" in html


# --- export campaign ---------------------------------------------------------


def test_export_campaign_repo_side_is_just_the_two_docs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    res = _export("campaign", "--game", str(FIXTURE_GAME), "--out", str(tmp_path / "out"))
    assert res.exit_code == 0, res.stdout
    payload = json.loads(res.stdout)
    html = Path(payload["file"]).read_text()
    assert _no_external_refs(html)
    assert "Milltown" in html          # adventure.md phrase
    assert "the Mayor is asking" in html or "Mayor" in html  # quest-board.md phrase


def test_export_campaign_inside_world_lists_offered_quest(wroot):
    res = runner.invoke(app, [
        "quest", "offer", "--title", "Clear the Cave", "--desc", "goblins are a problem",
        "--giver", "world", "--spawn", "--items", "torch",
    ])
    assert res.exit_code == 0, res.stdout

    res = _export("campaign")
    assert res.exit_code == 0, res.stdout
    html = Path(json.loads(res.stdout)["file"]).read_text()
    assert "Clear the Cave" in html
    assert "offered" in html.lower()


# --- shared behavior -----------------------------------------------------------


def test_export_default_out_dir_is_exports(wroot):
    res = _export("world")
    payload = json.loads(res.stdout)
    assert Path(payload["file"]).parent == wroot / "exports"


def test_export_no_external_refs_in_all_three(wroot):
    runner.invoke(app, [
        "quest", "offer", "--title", "Board Quest", "--desc", "x",
        "--giver", "world", "--spawn",
    ])
    for kind in ("game", "world", "campaign"):
        res = _export(kind)
        assert res.exit_code == 0, res.stdout
        html = Path(json.loads(res.stdout)["file"]).read_text()
        assert _no_external_refs(html)


# --- HTML escaping / markdown hardening (review fixes) -----------------------


def test_export_game_escapes_malicious_class_feature_tag(tmp_path, monkeypatch):
    game_dir = tmp_path / "evilgame"
    shutil.copytree(FIXTURE_GAME, game_dir)

    fighter_path = game_dir / "ruleset" / "classes" / "fighter.yaml"
    fighter_path.write_text(
        fighter_path.read_text().replace(
            "1: {features: [second_wind], spells: [], slots: {}}",
            '1: {features: [second_wind, "x<script>alert(1)</script>"], spells: [], slots: {}}',
        )
    )
    features_path = game_dir / "ruleset" / "features.yaml"
    features_path.write_text(
        features_path.read_text()
        + '\n"x<script>alert(1)</script>": {description: "malicious tag"}\n'
    )

    monkeypatch.chdir(tmp_path)
    res = _export("game", "--game", str(game_dir), "--out", str(tmp_path / "out"))
    assert res.exit_code == 0, res.stdout
    html = Path(json.loads(res.stdout)["file"]).read_text()

    assert "<script" not in html.lower()          # no live script tag reaches the page
    assert "&lt;script&gt;" in html.lower()       # the payload itself survives, escaped
    assert "alert(1)" in html.lower()             # confirms it's the same payload, just inert


def test_export_game_escapes_dc_label_html(tmp_path, monkeypatch):
    game_dir = tmp_path / "evildc"
    shutil.copytree(FIXTURE_GAME, game_dir)

    core_path = game_dir / "ruleset" / "core.yaml"
    core_path.write_text(
        core_path.read_text().replace(
            "dcs: {easy: 10, medium: 13, hard: 16}",
            'dcs: {easy: 10, medium: 13, hard: 16, "boss<b>bold</b>": 20}',
        )
    )

    monkeypatch.chdir(tmp_path)
    res = _export("game", "--game", str(game_dir), "--out", str(tmp_path / "out"))
    assert res.exit_code == 0, res.stdout
    html = Path(json.loads(res.stdout)["file"]).read_text()

    assert "<b>bold</b>" not in html
    assert "&lt;b&gt;bold&lt;/b&gt;" in html.lower()
    assert "(DC 20)" in html                       # generated parens/format survive untouched


def test_export_world_markdown_strips_script_capable_html(tmp_path, monkeypatch):
    game_dir = tmp_path / "evilmd"
    shutil.copytree(FIXTURE_GAME, game_dir)

    setting_path = game_dir / "content" / "setting.md"
    setting_path.write_text(
        setting_path.read_text()
        + "\n\nTrouble is brewing — the elders are worried.\n\n"
        + "<script>evil()</script>\n\n"
        + '<a href="javascript:x" onclick="y">link</a>\n\n'
        + "## A Real Heading\n"
    )

    monkeypatch.chdir(tmp_path)
    res = _export("world", "--game", str(game_dir), "--out", str(tmp_path / "out"))
    assert res.exit_code == 0, res.stdout
    html = Path(json.loads(res.stdout)["file"]).read_text()

    assert "evil()" not in html
    assert "<script" not in html.lower()
    assert "onclick" not in html.lower()
    assert "javascript:" not in html.lower()
    assert "<h2>A Real Heading</h2>" in html        # legit markdown still renders
    assert "Sunbleached Hills" in html              # no over-escaping regression on existing content
    assert "—" in html                              # em-dashes in setting.md still render raw
