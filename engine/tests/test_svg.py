import json

from typer.testing import CliRunner

from ttrpg_engine import render, worldfs
from ttrpg_engine.cli import app
from test_grid_render import ENC

runner = CliRunner()


def test_svg_contains_tokens_and_walls():
    svg = render.svg_map(ENC)
    assert svg.startswith("<svg")
    assert svg.count('class="tok"') == 2       # one PC, one live monster
    assert "pc-brin" in svg


def test_write_svg_stamps_and_indexes(wroot):
    worldfs.write_yaml(wroot / "state" / "encounter.yaml", ENC)
    res = runner.invoke(app, ["map", "render", "--svg"])
    assert res.exit_code == 0, res.stdout
    path = json.loads(res.stdout)["svg"]
    assert path.endswith("1203-04-17-skirmish-r01.svg")
    index = (wroot / "renders" / "index.html").read_text()
    assert "1203-04-17-skirmish-r01.svg" in index


def test_dead_monsters_not_drawn():
    enc = json.loads(json.dumps(ENC))
    enc["monsters"]["goblin-1"]["dead"] = True
    assert render.svg_map(enc).count('class="tok"') == 1


def test_caption_escapes_author_name():
    # the standalone/exported SVG (caption on) embeds the encounter name in its
    # footer and is opened directly in a browser via renders/index.html, so the
    # author-controlled name must be escaped there.
    enc = json.loads(json.dumps(ENC))
    enc["name"] = "Rats </text><img src=x onerror=alert(1)><text>"
    svg = render.svg_map(enc)                 # caption=True by default
    assert "<img" not in svg
    assert "&lt;img" in svg


def test_caption_off_omits_author_name():
    # the live viewer turns the caption off; the name must then not appear in
    # the SVG at all (it rides in JSON the client escapes via textContent).
    enc = json.loads(json.dumps(ENC))
    enc["name"] = "Skirmish <img src=x>"
    svg = render.svg_map(enc, caption=False)
    assert "img" not in svg and "Skirmish" not in svg
