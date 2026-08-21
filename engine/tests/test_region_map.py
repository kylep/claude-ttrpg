import json

from typer.testing import CliRunner

from ttrpg_engine import game, region_map, viewer_data, worldfs
from ttrpg_engine.cli import app
from ttrpg_engine.errors import EngineError
from conftest import FIXTURE_GAME, make_pc

runner = CliRunner()


def _g():
    return game.load(FIXTURE_GAME)


# ---------------------------------------------------------------------------
# visited derivation
# ---------------------------------------------------------------------------

def test_visited_starts_at_start_location(wroot):
    make_pc()
    assert region_map.visited_nodes(wroot, _g()) == {"town"}


def test_visited_grows_with_travel_delta(wroot):
    make_pc()
    res = runner.invoke(app, ["travel", "--to", "cave"])
    assert res.exit_code == 0, res.stdout
    assert region_map.visited_nodes(wroot, _g()) == {"town", "cave"}


def test_visited_falls_back_to_summary_parse(wroot):
    # an old world's travel event has no structured delta — the summary carries it
    make_pc()
    from ttrpg_engine import timeline
    timeline.append_event(wroot, type_="travel", actors=[],
                          summary="party travels town -> cave (4h)")
    assert "cave" in region_map.visited_nodes(wroot, _g())


# ---------------------------------------------------------------------------
# lenses / fog of war
# ---------------------------------------------------------------------------

def test_gm_sees_all_player_gets_fog(wroot):
    make_pc()
    gm = region_map.svg(wroot, _g(), "gm")
    assert 'data-ref="town"' in gm and 'data-ref="cave"' in gm

    player = region_map.svg(wroot, _g(), "player")
    assert 'data-ref="town"' in player          # visited: full + clickable
    assert 'data-ref="cave"' not in player      # rumored: not clickable
    assert "Cave?" in player                    # ...but named as a rumor
    assert "YOU ARE HERE" in player


def test_player_map_hides_unconnected_nodes(wroot):
    # add a node with no edge to anything visited: players must not see it at all
    region_path = wroot / "canon" / "maps" / "region.yaml"
    region = worldfs.read_yaml(region_path)
    region["nodes"]["far-keep"] = {"name": "Far Keep", "coords": [4, 6],
                                   "terrain": "settlement"}
    worldfs.write_yaml(region_path, region)
    make_pc()
    player = region_map.svg(wroot, _g(), "player")
    assert "Far Keep" not in player
    assert "Far Keep" in region_map.svg(wroot, _g(), "gm")


def test_render_is_deterministic_and_escaped(wroot):
    make_pc()
    region_path = wroot / "canon" / "maps" / "region.yaml"
    region = worldfs.read_yaml(region_path)
    region["nodes"]["town"]["name"] = 'Town <script>alert(1)</script>'
    region["nodes"]["town"]["terrain"] = "volcano"    # unknown type -> cairn fallback
    worldfs.write_yaml(region_path, region)
    a = region_map.svg(wroot, _g(), "gm")
    b = region_map.svg(wroot, _g(), "gm")
    assert a == b                                     # same state, same map
    assert "<script" not in a and "&lt;script&gt;" in a


def test_cli_map_region(wroot):
    make_pc()
    res = runner.invoke(app, ["map", "region", "--lens", "player"])
    assert res.exit_code == 0, res.stdout
    payload = json.loads(res.stdout)
    assert payload["visited"] == ["town"]
    assert (wroot / "renders" / "region.svg").exists()


# ---------------------------------------------------------------------------
# GM-only zone-index overlay
# ---------------------------------------------------------------------------

def test_zone_overlay_gm_only_and_hidden_by_default(wroot):
    make_pc()
    gm = region_map.svg(wroot, _g(), "gm")
    # the overlay group ships in the GM map, hidden until the client toggles it
    assert 'class="zone-overlay"' in gm
    assert 'style="display:none"' in gm
    assert "ZONE INDEX" in gm
    # players must NEVER receive the overlay (server is the trust boundary)
    player = region_map.svg(wroot, _g(), "player")
    assert "zone-overlay" not in player
    assert "ZONE INDEX" not in player
    assert region_map._BAND_COLOR["4-7"] not in player


def test_zone_overlay_rings_encode_band_and_status(wroot):
    make_pc()
    gm = region_map.svg(wroot, _g(), "gm")
    # town is 1-3/playable, cave is 4-7/stub (fixture) — each colour appears on a
    # node ring AND its legend swatch, so >= 2 occurrences
    assert gm.count(region_map._BAND_COLOR["1-3"]) >= 2
    assert gm.count(region_map._BAND_COLOR["4-7"]) >= 2
    # stub status renders a dotted ring (dash "1.5 5"): cave ring + legend key
    assert gm.count('stroke-dasharray="1.5 5"') >= 2


def test_zone_overlay_fails_open_on_untagged_node(wroot):
    # a node with no band must be skipped, not crash the render
    region_path = wroot / "canon" / "maps" / "region.yaml"
    region = worldfs.read_yaml(region_path)
    region["nodes"]["mystery"] = {"name": "Mystery", "coords": [3, 5],
                                  "terrain": "settlement"}
    worldfs.write_yaml(region_path, region)
    make_pc()
    gm = region_map.svg(wroot, _g(), "gm")          # no exception
    assert 'class="zone-overlay"' in gm
    assert "Mystery" in gm                           # node still on the base map


# ---------------------------------------------------------------------------
# location entity cards
# ---------------------------------------------------------------------------

def test_location_card_lenses(wroot):
    make_pc()
    g = _g()
    card = viewer_data.entity_card(wroot, g, "town", "player")
    assert card["kind"] == "location" and card["party_here"] is True
    assert card["description"] and card["connections"][0]["id"] == "cave"

    rumor = viewer_data.entity_card(wroot, g, "cave", "player")
    assert rumor.get("rumored") is True
    assert "description" not in rumor and "connections" not in rumor

    full = viewer_data.entity_card(wroot, g, "cave", "gm")
    assert full.get("rumored") is None and full["description"]
    assert isinstance(full.get("npcs"), list)         # GM lens lists locals

    # beyond the fog entirely: cut the edge and the player can't resolve cave
    region_path = wroot / "canon" / "maps" / "region.yaml"
    region = worldfs.read_yaml(region_path)
    region["edges"] = []
    worldfs.write_yaml(region_path, region)
    try:
        viewer_data.entity_card(wroot, g, "cave", "player")
        raise AssertionError("should have raised")
    except EngineError as e:
        assert e.code == "not_found"


def test_location_card_art_sanitized(wroot):
    make_pc()
    art = wroot / "canon" / "art"
    art.mkdir(parents=True)
    (art / "town.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
        '<script>alert(1)</script>'
        '<foreignObject><body onload="x()">hi</body></foreignObject>'
        '<circle cx="5" cy="5" r="4" onload="pwn()"/></svg>')
    card = viewer_data.entity_card(wroot, _g(), "town", "player")
    svg = card["art_svg"]
    assert "<circle" in svg
    assert "<script" not in svg
    assert "foreignObject" not in svg.lower()
    assert "onload" not in svg


def test_snapshot_carries_region_svg_only_off_combat(wroot):
    make_pc()
    g = _g()
    snap = viewer_data.state_snapshot(wroot, g, "player")
    assert snap.get("region_svg") and snap["map_svg"] is None
    res = runner.invoke(app, ["--seed", "5", "encounter", "start",
                              "maps/encounters/skirmish.yaml"])
    assert res.exit_code == 0, res.stdout
    snap = viewer_data.state_snapshot(wroot, g, "player")
    assert snap["map_svg"] and "region_svg" not in snap


def test_story_reveal_location(wroot):
    make_pc()
    res = runner.invoke(app, ["story", "reveal", "--location", "town"])
    assert res.exit_code == 0, res.stdout
    entry = json.loads(res.stdout)
    assert entry["type"] == "location" and entry["ref"] == "town"
    res = runner.invoke(app, ["story", "reveal", "--location", "atlantis"])
    assert res.exit_code == 1


def test_location_card_banner_fail_open(wroot):
    # a location that declares a `banner` carries it on its card, fail-open to
    # None when the image file doesn't exist under the game content dir.
    make_pc()
    g = _g()
    region_path = wroot / "canon" / "maps" / "region.yaml"
    region = worldfs.read_yaml(region_path)
    region["nodes"]["town"]["banner"] = "art/banners/town.png"   # no such file in the fixture
    worldfs.write_yaml(region_path, region)
    card = viewer_data.entity_card(wroot, g, "town", "player")
    assert "banner" in card and card["banner"] is None
