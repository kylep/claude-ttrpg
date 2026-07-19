"""Print-book PDF export: renders designed booklet PDFs (world, classes, races,
bestiary) from a game's content via WeasyPrint. Pure read + render; no state
mutation. Images resolve fail-open — a missing file degrades to text."""

from pathlib import Path

from weasyprint import HTML

from ttrpg_engine.markdown_render import esc

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


_PALETTE = {
    "ink": "#22201c", "rule": "#9c8560", "frame": "#cdbfa0",
    "accent": "#6b4f2a", "paper": "#fdfbf5", "band": "#efe4cc",
    "cover_bg": "#1a1613", "cover_ink": "#f4ecd8", "cover_title": "#e8b04b",
}


def _book_style() -> str:
    return _font_face_css() + f"""
@page {{
  size: A4;
  margin: 22mm 20mm 20mm;
  @bottom-center {{ content: counter(page); color: {_PALETTE['accent']};
    font-family: Georgia, serif; font-size: 9pt; }}
  @top-center {{ content: string(section); color: {_PALETTE['rule']};
    font-family: 'Cinzel', Georgia, serif; font-size: 8pt;
    letter-spacing: 0.15em; text-transform: uppercase; }}
}}
@page cover {{ margin: 0; @bottom-center {{ content: none; }} @top-center {{ content: none; }} }}
* {{ box-sizing: border-box; }}
body {{ font-family: Georgia, 'Times New Roman', serif; color: {_PALETTE['ink']};
  line-height: 1.5; }}
.section-title {{ string-set: section content(text); }}
h1, h2, h3 {{ font-family: 'Cinzel', Georgia, serif; }}
h2 {{ border-bottom: 2px solid {_PALETTE['rule']}; padding-bottom: 0.2rem;
  margin-top: 1.6rem; color: {_PALETTE['accent']}; }}
h3 {{ color: {_PALETTE['accent']}; margin: 0 0 0.25rem; }}
.cover {{ page: cover; height: 297mm; width: 210mm; position: relative;
  background: {_PALETTE['cover_bg']}; color: {_PALETTE['cover_ink']};
  display: flex; flex-direction: column; justify-content: flex-end; }}
.cover img.banner {{ position: absolute; top: 0; left: 0; width: 210mm;
  height: 297mm; object-fit: cover; }}
.cover .plate {{ position: relative; margin: 0 0 40mm; padding: 10mm 16mm;
  background: linear-gradient(transparent, rgba(0,0,0,0.72) 30%); }}
.cover h1 {{ font-size: 46pt; font-weight: 700; letter-spacing: 0.04em;
  color: {_PALETTE['cover_title']}; margin: 0;
  text-shadow: 0 2px 8px rgba(0,0,0,0.8); }}
.cover .subtitle {{ font-size: 13pt; font-style: italic;
  color: {_PALETTE['cover_ink']}; margin-top: 0.4rem; }}
.content {{ page-break-before: always; }}
.card {{ border: 1px solid {_PALETTE['frame']}; border-radius: 6px;
  padding: 0.7rem 1rem; margin: 0.85rem 0; background: #fffdf8;
  break-inside: avoid; }}
.roster {{ display: block; }}
.roster .card {{ overflow: hidden; }}
.roster img.portrait {{ float: left; width: 42mm; height: 42mm;
  object-fit: cover; border: 1px solid {_PALETTE['frame']}; border-radius: 4px;
  margin: 0 1rem 0.5rem 0; }}
.tag {{ display: inline-block; background: {_PALETTE['band']}; border-radius: 3px;
  padding: 0.05rem 0.5rem; font-size: 0.82em; margin: 0 0.25rem 0.25rem 0; }}
table {{ border-collapse: collapse; width: 100%; margin: 0.8rem 0; }}
th, td {{ border: 1px solid {_PALETTE['frame']}; padding: 0.35rem 0.6rem;
  text-align: left; vertical-align: top; }}
th {{ background: {_PALETTE['band']}; }}
.fullbleed {{ page-break-before: always; text-align: center; }}
.fullbleed img {{ max-width: 100%; max-height: 250mm; }}
p.lead::first-letter {{ font-family: 'Cinzel', Georgia, serif; font-size: 3.2em;
  line-height: 0.8; float: left; padding: 0.05em 0.08em 0 0; color: {_PALETTE['accent']}; }}
"""


def _content_image(content_dir, rel):
    if not (isinstance(rel, str) and rel):
        return None
    try:
        return rel if (Path(content_dir) / rel).exists() else None
    except OSError:
        return None


def _cover_html(title, subtitle, cover_rel):
    banner = f'<img class="banner" src="{esc(cover_rel)}" alt="">' if cover_rel else ""
    return (
        f'<div class="cover">{banner}'
        f'<div class="plate"><h1>{esc(title)}</h1>'
        f'<div class="subtitle">{esc(subtitle)}</div></div></div>'
    )


def _document(title, subtitle, cover_rel, body):
    return (
        f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        f"<title>{esc(title)}</title><style>{_book_style()}</style></head>"
        f"<body>{_cover_html(title, subtitle, cover_rel)}"
        f"<div class='content'><h2 class='section-title'>{esc(title)}</h2>{body}</div>"
        f"</body></html>"
    )


def render_pdf(html, content_dir):
    return HTML(string=html, base_url=str(content_dir)).write_pdf()


def page_count(html, content_dir):
    return len(HTML(string=html, base_url=str(content_dir)).render().pages)
