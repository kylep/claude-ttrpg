"""Print-book PDF export: renders designed booklet PDFs (world, classes, races,
bestiary) from a game's content via WeasyPrint. Pure read + render; no state
mutation. Images resolve fail-open — a missing file degrades to text."""

from pathlib import Path

from weasyprint import HTML

from ttrpg_engine import chargen, game as game_mod
from ttrpg_engine.markdown_render import esc, render_markdown as _md

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
p.lead::first-letter {{ font-family: 'Cinzel', Georgia, serif; font-size: 1.6em;
  padding: 0 0.03em 0 0; color: {_PALETTE['accent']}; }}
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


def _title_case(tag):
    return tag.replace("_", " ").title()


def _roster_card(name, img_rel, body_html):
    img = f'<img class="portrait" src="{esc(img_rel)}" alt="">' if img_rel else ""
    return f'<div class="card"><h3>{esc(name)}</h3>{img}{body_html}</div>'


def build_races(src):
    g, content_dir = src["g"], src["content_dir"]
    lore = chargen._load_race_lore(g)
    cover = _content_image(content_dir, "art/covers/races.png")
    cards = []
    for name, race in sorted(g["races"].items()):
        entry = lore.get(name, {}) if isinstance(lore, dict) else {}
        img = _content_image(content_dir, entry.get("image"))
        appearance = entry.get("appearance", "").strip()
        bonuses = ", ".join(f"{k} +{v}" for k, v in race.get("bonuses", {}).items()) or "—"
        desc = esc(race.get("description", ""))
        appear = f"<p class='lead'>{esc(appearance)}</p>" if appearance else ""
        body = (
            f"<p>{desc}</p>{appear}"
            f"<p><span class='tag'>Ability bonuses: {esc(bonuses)}</span>"
            f"<span class='tag'>Speed {race['speed']}</span></p>"
        )
        cards.append(_roster_card(name.title(), img, body))
    body = f"<div class='roster'>{''.join(cards)}</div>"
    html = _document("Races", src["world_name"] or g["meta"]["name"].title(), cover, body)
    return render_pdf(html, content_dir)


def build_bestiary(src):
    g, content_dir = src["g"], src["content_dir"]
    cover = _content_image(content_dir, "art/covers/bestiary.png")
    cards = []
    for mid, mon in sorted(game_mod.bestiary(g).items()):
        img = _content_image(content_dir, mon.get("image"))
        attacks = "; ".join(
            f"{a['name']} (+{a['attack_mod']}, {a['damage']}, range {a['range']})"
            for a in mon.get("attacks", [])
        ) or "—"
        notes = f"<p><strong>Notes:</strong> {esc(mon['notes'].strip())}</p>" if mon.get("notes") else ""
        body = (
            f"<p>{esc(mon.get('description', ''))}</p>"
            f"<p><span class='tag'>AC {mon['ac']}</span><span class='tag'>HP {mon['hp']}</span>"
            f"<span class='tag'>Speed {mon['speed']}</span><span class='tag'>XP {mon['xp']}</span>"
            f"<span class='tag'>{esc(mon.get('difficulty', '?'))}</span></p>"
            f"<p><strong>Attacks:</strong> {esc(attacks)}</p>{notes}"
        )
        cards.append(_roster_card(mon.get("name", mid.title()), img, body))
    body = f"<div class='roster'>{''.join(cards)}</div>"
    html = _document("Bestiary", src["world_name"] or g["meta"]["name"].title(), cover, body)
    return render_pdf(html, content_dir)


def build_classes(src):
    g, content_dir = src["g"], src["content_dir"]
    cover = _content_image(content_dir, "art/covers/classes.png")
    cards = []
    for name, cls in sorted(g["classes"].items()):
        gear = ", ".join(_title_case(i) for i in cls.get("starting_gear", [])) or "—"
        skills = ", ".join(_title_case(s) for s in cls.get("skills", []))
        cards.append(
            f"<div class='card'><h3>{esc(name.title())}</h3>"
            f"<p class='lead'>{esc(cls.get('description', '').strip())}</p>"
            f"<p><span class='tag'>Hit die d{cls['hit_die']}</span>"
            f"<span class='tag'>Start gold {cls.get('starting_gold', 0)} gp</span></p>"
            f"<p><strong>Starting gear:</strong> {esc(gear)}.</p>"
            f"<p><strong>Skills:</strong> choose {cls.get('skill_choices', 0)} from {esc(skills)}.</p>"
            f"</div>"
        )
    body = "".join(cards)
    html = _document("Classes", src["world_name"] or g["meta"]["name"].title(), cover, body)
    return render_pdf(html, content_dir)


def _world_lore_html(content_dir):
    parts = []
    for fname, heading in (("setting.md", "The Setting"), ("history.md", "History")):
        path = content_dir / fname
        if path.exists():
            parts.append(f"<h3>{heading}</h3>{_md(path.read_text())}")
    if not parts:
        return "<p><em>World lore is still being written.</em></p>"
    return "".join(parts)


def _world_svg_html(content_dir):
    svg_path = content_dir / "maps" / "world-map.svg"
    if not svg_path.exists():
        return ""
    # Inline the SVG at a constrained size so it sits small at the top.
    return f"<div style='max-width:120mm;margin:0 auto 1rem'>{svg_path.read_text()}</div>"


def _world_html(src):
    g, content_dir = src["g"], src["content_dir"]
    cover = _content_image(content_dir, "art/covers/world.png")
    svg = _world_svg_html(content_dir)
    lore = _world_lore_html(content_dir)
    body = f"{svg}{lore}"
    painted = _content_image(content_dir, "maps/WorldMapPainted.png")
    if painted:
        body += f"<div class='fullbleed'><img src='{esc(painted)}' alt='World map'></div>"
    return _document("The World", src["world_name"] or g["meta"]["name"].title(), cover, body)


def build_world(src):
    return render_pdf(_world_html(src), src["content_dir"])
