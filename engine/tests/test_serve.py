import http.client
import json
import threading
import time

import pytest
from typer.testing import CliRunner

from ttrpg_engine import combat, serve, worldfs
from ttrpg_engine.cli import app
from conftest import make_pc

runner = CliRunner()


@pytest.fixture
def live(wroot):
    """A viewer server for wroot on an ephemeral port."""
    server = serve.run(wroot, 0)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield wroot, port
    server.shutdown()


def _get(port, path):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", path)
    resp = conn.getresponse()
    body = resp.read()
    conn.close()
    return resp.status, body


def test_pages_served(live):
    _, port = live
    for path in ("/", "/gm"):
        status, body = _get(port, path)
        assert status == 200
        assert b"claude-ttrpg" in body


def test_state_lenses_diverge_on_hidden_monster(live):
    wroot, port = live
    make_pc()
    res = runner.invoke(app, ["--seed", "5", "encounter", "start",
                              "maps/encounters/hideout.yaml"])
    assert res.exit_code == 0, res.stdout
    combat.set_effect(wroot, "goblin-1", "hidden", -1)

    status, body = _get(port, "/api/state?lens=player")
    assert status == 200
    player = json.loads(body)
    roster_ids = {f["id"] for f in player["encounter"]["roster"]}
    assert "goblin-1" not in roster_ids and "goblin_archer-1" in roster_ids
    assert "goblin-1" not in player["map_svg"]
    assert "internals" not in player and "timeline" not in player
    foe = next(f for f in player["encounter"]["roster"] if f["id"] == "goblin_archer-1")
    assert "status" in foe and "hp" not in foe

    status, body = _get(port, "/api/state?lens=gm")
    gm = json.loads(body)
    gm_ids = {f["id"] for f in gm["encounter"]["roster"]}
    assert "goblin-1" in gm_ids
    assert "internals" in gm and "timeline" in gm
    foe = next(f for f in gm["encounter"]["roster"] if f["id"] == "goblin-1")
    assert foe["hp"] == 7


def test_story_endpoint_degrades_without_transcripts(live):
    _, port = live
    status, body = _get(port, "/api/story")
    assert status == 200
    data = json.loads(body)
    assert data["entries"] == []
    assert data["cursor"]["file"] is None


def test_events_stream_ticks_on_state_change(live):
    wroot, port = live
    make_pc()
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", "/events")
    resp = conn.getresponse()
    assert resp.status == 200
    assert b"retry:" in resp.fp.readline()
    resp.fp.readline()

    time.sleep(0.5)                                       # let the baseline settle
    combat.set_effect(wroot, "pc-borin", "blessed", 3)    # a state write
    deadline = time.time() + 5
    seen = b""
    while time.time() < deadline and b"event: state" not in seen:
        seen += resp.fp.readline()
    conn.close()
    assert b"event: state" in seen


def test_renders_path_traversal_rejected(live):
    wroot, port = live
    (wroot / "renders").mkdir(exist_ok=True)
    (wroot / "renders" / "ok.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>")
    status, _ = _get(port, "/renders/ok.svg")
    assert status == 200
    status, _ = _get(port, "/renders/../world.yaml")
    assert status == 404
    status, _ = _get(port, "/renders/%2e%2e/world.yaml")
    assert status == 404


def test_unknown_route_404(live):
    _, port = live
    status, _ = _get(port, "/api/nope")
    assert status == 404


def test_map_svg_escapes_author_name_against_xss(live):
    wroot, port = live
    make_pc()
    res = runner.invoke(app, ["--seed", "5", "encounter", "start",
                              "maps/encounters/skirmish.yaml"])
    assert res.exit_code == 0, res.stdout
    enc = worldfs.read_yaml(wroot / "state" / "encounter.yaml")
    enc["name"] = "Rats </text><img src=x onerror=alert(1)><text>"
    worldfs.write_yaml(wroot / "state" / "encounter.yaml", enc)
    status, body = _get(port, "/api/state?lens=player")
    assert status == 200
    svg = json.loads(body)["map_svg"]
    assert "<img" not in svg                                    # no real tag can break out
    assert "&lt;img" in svg                                     # escaped to inert text instead


def test_story_endpoint_carries_lens(live):
    _, port = live
    # no transcript in a test world, but the param must be accepted, not 500
    for lens in ("player", "gm"):
        status, body = _get(port, "/api/story?lens=" + lens)
        assert status == 200
        assert json.loads(body)["cursor"]["file"] is None
