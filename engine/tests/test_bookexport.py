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
