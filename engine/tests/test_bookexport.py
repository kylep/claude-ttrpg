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
