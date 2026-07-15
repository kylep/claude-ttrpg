import hashlib
import json

from typer.testing import CliRunner

from ttrpg_engine import combat, timeline, viewer_data, worldfs
from ttrpg_engine.cli import app
from conftest import make_pc

runner = CliRunner()


def _game(wroot):
    return worldfs.load_game_for(wroot)


def _start(wroot):
    make_pc()
    res = runner.invoke(app, ["--seed", "5", "encounter", "start",
                              "maps/encounters/skirmish.yaml"])
    assert res.exit_code == 0, res.stdout


def _enc(wroot):
    return worldfs.read_yaml(wroot / "state" / "encounter.yaml")


def _put_enc(wroot, enc):
    worldfs.write_yaml(wroot / "state" / "encounter.yaml", enc)


def _roster_ids(snap):
    return [e["id"] for e in snap["encounter"]["roster"]]


def _entry(snap, cid):
    return next(e for e in snap["encounter"]["roster"] if e["id"] == cid)


def _legend_ids(snap):
    return [t["id"] for t in snap["encounter"]["legend"]]


def test_no_encounter_snapshot(wroot):
    make_pc()
    snap = viewer_data.state_snapshot(wroot, _game(wroot), "player")
    assert snap["lens"] == "player"
    assert snap["encounter"] is None and snap["map_svg"] is None
    assert snap["world"] == "Test World"
    assert snap["clock"] == {"date": "1203-04-17", "hour": 9}
    assert snap["location"] == "Town"          # slug title-cased for display
    assert snap["party_gold"] == 0 and snap["stash"] == []
    assert snap["quests"] == []
    assert [pc["id"] for pc in snap["party"]] == ["pc-borin"]
    assert snap["party"][0]["hp"] == snap["party"][0]["max_hp"]
    assert "internals" not in snap and "timeline" not in snap
    gm = viewer_data.state_snapshot(wroot, _game(wroot), "gm")
    assert gm["lens"] == "gm"
    assert gm["internals"] == {"stealth": {}, "grapples": {}, "sneak_used": {},
                               "gear_actions": {}, "aloft": {}}
    assert isinstance(gm["timeline"], list)
    # anything that is not "gm" is the player lens
    assert viewer_data.state_snapshot(wroot, _game(wroot), "spectator")["lens"] == "player"


def test_player_lens_hides_hidden_monster_gm_sees_it(wroot):
    _start(wroot)
    combat.set_effect(wroot, "goblin-1", "hidden", -1)
    combat.set_effect(wroot, "pc-borin", "hidden", -1)

    snap = viewer_data.state_snapshot(wroot, _game(wroot), "player")
    assert "goblin-1" not in _roster_ids(snap)
    assert "goblin-2" in _roster_ids(snap)
    # the viewer SVG carries only glyphs; identity lives in the legend. The
    # masking must reach the drawn map: one token per visible roster entry.
    assert "goblin-1" not in _legend_ids(snap)
    assert "goblin-2" in _legend_ids(snap)
    assert snap["map_svg"].count('class="tok"') == len(snap["encounter"]["roster"])
    # hidden PCs pass through — players know their own rogue
    assert "pc-borin" in _roster_ids(snap)
    assert "pc-borin" in _legend_ids(snap)
    assert "hidden" in _entry(snap, "pc-borin")["effects"]
    assert "internals" not in snap and "timeline" not in snap

    gm = viewer_data.state_snapshot(wroot, _game(wroot), "gm")
    assert "goblin-1" in _roster_ids(gm)
    assert "goblin-1" in _legend_ids(gm)
    assert gm["map_svg"].count('class="tok"') == len(gm["encounter"]["roster"])
    g1 = _entry(gm, "goblin-1")
    assert g1["hp"] == 7 and g1["max_hp"] == 7
    assert "hidden" in g1["effects"]
    assert set(gm["internals"]) == {"stealth", "grapples", "sneak_used",
                                    "gear_actions", "aloft"}


def test_player_encounter_filter_is_pure(wroot):
    _start(wroot)
    combat.set_effect(wroot, "goblin-1", "hidden", -1)
    enc = _enc(wroot)
    before = json.dumps(enc, sort_keys=True, default=str)
    view = viewer_data.player_encounter(enc)
    assert "goblin-1" not in view["monsters"]
    assert "goblin-1" not in view["positions"]
    assert "goblin-1" not in view["order"]
    for key in ("stealth", "grapples", "sneak_used", "gear_actions"):
        assert key not in view
    assert json.dumps(enc, sort_keys=True, default=str) == before


def test_monster_status_thresholds(wroot):
    _start(wroot)
    enc = _enc(wroot)
    enc["monsters"]["goblin-1"]["max_hp"] = 6
    for hp, word in [(6, "healthy"), (5, "healthy"), (4, "wounded"),
                     (2, "bloodied"), (1, "bloodied")]:
        enc["monsters"]["goblin-1"]["hp"] = hp
        _put_enc(wroot, enc)
        snap = viewer_data.state_snapshot(wroot, _game(wroot), "player")
        entry = _entry(snap, "goblin-1")
        assert entry["status"] == word, (hp, word)
        assert "hp" not in entry and "max_hp" not in entry
    enc["monsters"]["goblin-1"]["dead"] = True
    _put_enc(wroot, enc)
    snap = viewer_data.state_snapshot(wroot, _game(wroot), "player")
    assert _entry(snap, "goblin-1")["status"] == "down"
    assert _entry(snap, "goblin-1")["dead"] is True


def test_pc_always_has_hp_and_up_matches_order(wroot):
    _start(wroot)
    for lens in ("player", "gm"):
        snap = viewer_data.state_snapshot(wroot, _game(wroot), lens)
        pc = _entry(snap, "pc-borin")
        assert pc["side"] == "pc" and pc["hp"] > 0 and pc["max_hp"] == pc["hp"]
        enc = _enc(wroot)
        assert snap["encounter"]["up"] == enc["order"][enc["turn"]]
        assert _roster_ids(snap) == enc["order"]


def test_quests_appear_after_offer(wroot):
    make_pc()
    res = runner.invoke(app, ["quest", "offer", "--title", "Clear the Rats",
                              "--desc", "rid the cellar of rats",
                              "--giver", "world", "--spawn", "--gold", "5"])
    assert res.exit_code == 0, res.stdout
    snap = viewer_data.state_snapshot(wroot, _game(wroot), "player")
    assert [q["id"] for q in snap["quests"]] == ["clear-the-rats"]
    quest = snap["quests"][0]
    assert quest["status"] == "offered"
    assert quest["escrow"] == {"gold": 0, "items": []}  # raw file, not the summary


def test_timeline_gm_only_capped_at_30(wroot):
    make_pc()
    for i in range(40):
        timeline.append_event(wroot, type_="note", summary=f"event {i}")
    gm = viewer_data.state_snapshot(wroot, _game(wroot), "gm")
    assert len(gm["timeline"]) == 30
    files = sorted((wroot / "timeline").glob("*.yaml"))
    assert [e["id"] for e in gm["timeline"]] == [p.stem for p in files[-30:]]
    assert gm["timeline"][-1] == {"id": files[-1].stem, "type": "note",
                                  "summary": "event 39"}
    player = viewer_data.state_snapshot(wroot, _game(wroot), "player")
    assert "timeline" not in player


def _hash_tree(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def test_snapshots_never_write(wroot):
    _start(wroot)
    combat.set_effect(wroot, "goblin-1", "hidden", -1)
    res = runner.invoke(app, ["quest", "offer", "--title", "Watch Duty",
                              "--desc", "hold the gate", "--giver", "world",
                              "--spawn", "--gold", "1",
                              "--deadline", "1203-04-18"])
    assert res.exit_code == 0, res.stdout
    g = _game(wroot)
    before = _hash_tree(wroot)
    for lens in ("player", "gm"):
        viewer_data.state_snapshot(wroot, g, lens)
        viewer_data.state_snapshot(wroot, g, lens)
    assert _hash_tree(wroot) == before


def test_hidden_monsters_turn_is_masked_for_players(wroot):
    make_pc()
    res = runner.invoke(app, ["--seed", "5", "encounter", "start",
                              "maps/encounters/hideout.yaml"])
    assert res.exit_code == 0, res.stdout
    combat.set_effect(wroot, "goblin-1", "hidden", -1)
    enc = worldfs.read_yaml(wroot / "state" / "encounter.yaml")
    enc["turn"] = enc["order"].index("goblin-1")
    worldfs.write_yaml(wroot / "state" / "encounter.yaml", enc)
    g = worldfs.load_game_for(wroot)
    assert viewer_data.state_snapshot(wroot, g, "player")["encounter"]["up"] == "???"
    assert viewer_data.state_snapshot(wroot, g, "gm")["encounter"]["up"] == "goblin-1"
