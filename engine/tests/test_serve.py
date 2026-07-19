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


def test_story_endpoint_empty_without_log(live):
    _, port = live
    status, body = _get(port, "/api/story")
    assert status == 200
    data = json.loads(body)
    assert data["entries"] == []
    assert data["cursor"] == {"offset": 0}


def test_story_endpoint_serves_posted_entries(live):
    _, port = live
    make_pc()                                  # auto-emits a character card entry
    res = runner.invoke(app, ["story", "narrate", "--text", "The door *creaks* open."])
    assert res.exit_code == 0, res.stdout
    status, body = _get(port, "/api/story")
    assert status == 200
    data = json.loads(body)
    types = [e["type"] for e in data["entries"]]
    assert types == ["character", "narration"]
    assert data["entries"][0]["ref"] == "pc-borin"
    assert "<em>creaks</em>" in data["entries"][1]["html"]
    # incremental read: same offset back means nothing new
    status, body = _get(port, "/api/story?offset=" + str(data["cursor"]["offset"]))
    again = json.loads(body)
    assert again["entries"] == [] and again["cursor"] == data["cursor"]


def test_entity_endpoint_cards_and_lens(live):
    wroot, port = live
    make_pc()
    status, body = _get(port, "/api/entity/pc-borin")
    assert status == 200
    card = json.loads(body)
    assert card["kind"] == "pc" and card["name"] == "Borin"
    status, _ = _get(port, "/api/entity/no-such-thing")
    assert status == 404
    # a hidden monster's card exists for the GM and 404s for players
    res = runner.invoke(app, ["--seed", "5", "encounter", "start",
                              "maps/encounters/hideout.yaml"])
    assert res.exit_code == 0, res.stdout
    combat.set_effect(wroot, "goblin-1", "hidden", -1)
    status, _ = _get(port, "/api/entity/goblin-1?lens=player")
    assert status == 404
    status, body = _get(port, "/api/entity/goblin-1?lens=gm")
    assert status == 200
    assert json.loads(body)["hp"] == 7
    # players get a status word, never numbers
    status, body = _get(port, "/api/entity/goblin_archer-1?lens=player")
    card = json.loads(body)
    assert "status" in card and "hp" not in card


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
    # the viewer SVG (caption off) embeds no author names at all — the encounter
    # name rides in JSON fields the client renders via textContent — so nothing
    # author-controlled can break out of the innerHTML'd map.
    assert "<img" not in svg
    assert "onerror" not in svg


def test_story_endpoint_carries_lens(live):
    _, port = live
    # empty log or not, the lens param must be accepted, not 500
    for lens in ("player", "gm"):
        status, body = _get(port, "/api/story?lens=" + lens)
        assert status == 200
        assert json.loads(body)["cursor"]["offset"] == 0


def test_content_art_route_serves_and_guards(live):
    wroot, port = live
    content = worldfs.load_game_for(wroot)["content_dir"]
    art_root = content / "art"
    # the game content dir is a shared fixture on disk — track whether art/
    # existed so the finally can fully remove anything this test created.
    preexisting = art_root.exists()
    (art_root / "bestiary").mkdir(parents=True, exist_ok=True)
    png = art_root / "bestiary" / "__viewer_test__.png"
    lore = art_root / "__viewer_test__.txt"
    # JPEG magic bytes under a .png name — the route must trust the bytes
    png.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF_fake_")
    lore.write_text("not an image")
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/art/bestiary/__viewer_test__.png")
        resp = conn.getresponse()
        body = resp.read()
        ctype = resp.getheader("Content-Type")
        conn.close()
        assert resp.status == 200 and body.startswith(b"\xff\xd8\xff")
        assert ctype == "image/jpeg"          # sniffed from bytes, not the .png suffix
        # a non-image suffix under art/ is refused (never serve yaml/lore/text)
        status, _ = _get(port, "/art/__viewer_test__.txt")
        assert status == 404
        # missing file, and path traversal out of the art dir
        status, _ = _get(port, "/art/bestiary/nope.png")
        assert status == 404
        status, _ = _get(port, "/art/../../world.yaml")
        assert status == 404
        status, _ = _get(port, "/art/%2e%2e/%2e%2e/world.yaml")
        assert status == 404
    finally:
        if preexisting:                     # leave a real art/ dir intact
            png.unlink(missing_ok=True)
            lore.unlink(missing_ok=True)
        else:                               # we created art/ — remove it wholesale
            import shutil
            shutil.rmtree(art_root, ignore_errors=True)
