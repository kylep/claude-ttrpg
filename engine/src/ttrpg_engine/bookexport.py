"""Print-book PDF export: renders designed booklet PDFs (world, classes, races,
bestiary) from a game's content via WeasyPrint. Pure read + render; no state
mutation. Images resolve fail-open — a missing file degrades to text."""

from pathlib import Path

_FONT_DIR = Path(__file__).parent / "assets" / "fonts"


def _font_face_css() -> str:
    """@font-face rule for the bundled Cinzel variable display font, using an
    absolute file URL so WeasyPrint finds it regardless of cwd. Returns "" if
    the TTF is absent, so the CSS font stack falls back to Georgia/serif and the
    build never fails on a missing font."""
    ttf = _FONT_DIR / "Cinzel.ttf"
    if not ttf.exists():
        return ""
    return (
        f"@font-face {{ font-family: 'Cinzel'; font-weight: 400 900; "
        f"src: url('file://{ttf}'); }}\n"
    )
