from weasyprint import HTML

from ttrpg_engine import bookexport


def test_weasyprint_renders_pdf_bytes():
    pdf = HTML(string="<h1>hello</h1>").write_pdf()
    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF")


def test_font_face_css_present_when_fonts_bundled():
    css = bookexport._font_face_css()
    assert "@font-face" in css
    assert "Cinzel" in css


from pathlib import Path

FAMILYRPG = Path("games/familyrpg")


def test_content_image_failopen(tmp_path):
    (tmp_path / "art").mkdir()
    (tmp_path / "art" / "x.png").write_bytes(b"\x89PNG")
    assert bookexport._content_image(tmp_path, "art/x.png") == "art/x.png"
    assert bookexport._content_image(tmp_path, "art/missing.png") is None
    assert bookexport._content_image(tmp_path, None) is None
    assert bookexport._content_image(tmp_path, "") is None


def test_cover_page_renders_with_missing_cover():
    html = bookexport._document("Bestiary", "The Known World", None, "<p>body</p>")
    pdf = bookexport.render_pdf(html, FAMILYRPG / "content")
    assert pdf.startswith(b"%PDF")
    assert bookexport.page_count(html, FAMILYRPG / "content") >= 2


from ttrpg_engine import export as export_mod


def _familyrpg_src():
    return export_mod.resolve_source(None, FAMILYRPG)


def test_build_races_pdf():
    pdf = bookexport.build_races(_familyrpg_src())
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 5000


def test_build_bestiary_pdf():
    pdf = bookexport.build_bestiary(_familyrpg_src())
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 5000


def test_roster_card_omits_missing_image():
    card = bookexport._roster_card("Orc", None, "<p>hi</p>")
    assert "<img" not in card
    assert "Orc" in card


def test_build_classes_pdf():
    pdf = bookexport.build_classes(_familyrpg_src())
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 5000


def test_build_world_pdf():
    pdf = bookexport.build_world(_familyrpg_src())
    assert pdf.startswith(b"%PDF")
    # cover + lore page + full-page painted map = at least 3 pages
    src = _familyrpg_src()
    html = bookexport._world_html(src)
    assert bookexport.page_count(html, src["content_dir"]) >= 3


def test_sections_registry_covers_all_four():
    assert set(bookexport.SECTIONS) == {"world", "classes", "races", "bestiary"}
    for _name, (builder, filename) in bookexport.SECTIONS.items():
        assert callable(builder)
        assert filename.endswith(".pdf")


from typer.testing import CliRunner
from ttrpg_engine.cli import app


def test_cli_export_book_all_writes_pdfs(tmp_path):
    out = tmp_path / "exports"
    res = CliRunner().invoke(
        app, ["export", "book", "all", "--game", "games/familyrpg", "--out", str(out)]
    )
    assert res.exit_code == 0, res.stdout
    for fn in ("world.pdf", "classes.pdf", "races.pdf", "bestiary.pdf"):
        assert (out / fn).exists(), fn
        assert (out / fn).read_bytes().startswith(b"%PDF")


def test_cli_export_book_rejects_unknown_section(tmp_path):
    res = CliRunner().invoke(
        app, ["export", "book", "bogus", "--game", "games/familyrpg", "--out", str(tmp_path)]
    )
    assert res.exit_code != 0
