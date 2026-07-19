# Print-book PDF Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render four designed booklet PDFs (World, Classes, Races, Bestiary) from committed content + committed cover art, via WeasyPrint, and remove the lossy Google Docs export path.

**Architecture:** A new `bookexport.py` module reuses the existing `export.resolve_source()` content loaders, applies print-book HTML templates + a paged CSS stylesheet, and renders to PDF bytes with WeasyPrint. Cover images and portraits live under `games/<game>/content/art/` (shared with the future web UI) and are resolved fail-open — a missing image degrades to text, never a hard failure. A new `engine export book <section>` CLI command drives it. Cover banners are generated once via the image-gen skill and committed.

**Tech Stack:** Python 3.11+, Typer CLI, WeasyPrint (PDF), PyYAML, `markdown`. Native dep: Pango/Cairo via Homebrew.

## Global Constraints

- Python floor: **>=3.11** (matches `engine/pyproject.toml`).
- Engine is invoked as `engine <cmd>` (installed console script) or `uv run --project engine engine <cmd>`. Tests run with `uv run --project engine pytest`.
- All content/art paths are **content-relative** (e.g. `art/bestiary/orc.png`) and resolved under the game's `content_dir`. Never embed absolute machine paths in committed files.
- Image resolution is **fail-open**: a missing/empty `image` field or missing file yields `None` and the template omits the image — never raises. Mirror the existing helpers `viewer_data._monster_image` and `chargen._race_image`.
- No state mutation in export code — pure read + render.
- Output filenames: `world.pdf`, `classes.pdf`, `races.pdf`, `bestiary.pdf`. Default out dir `exports/`.
- Cover art path convention: `art/covers/{world,classes,races,bestiary}.png` under `content/`.
- Font stack: `'Cinzel', Georgia, 'Times New Roman', serif` (display) and `Georgia, serif` (body). Font absence must not break the build.

---

## File Structure

- **Create** `engine/src/ttrpg_engine/bookexport.py` — section templates, book CSS, WeasyPrint render. One job: `src dict → styled PDF bytes`.
- **Create** `engine/src/ttrpg_engine/assets/fonts/` — bundled Cinzel display font (OFL).
- **Create** `engine/tests/test_bookexport.py` — unit tests.
- **Modify** `engine/pyproject.toml` — add `weasyprint` dependency.
- **Modify** `engine/src/ttrpg_engine/cli.py` — add `export book` subcommand.
- **Create** `games/familyrpg/content/art/covers/*.png` — 4 committed cover banners (Task 9, spend).
- **Replace** `.claude/skills/export-docs/SKILL.md` → `.claude/skills/export-pdf/SKILL.md`.

---

## Task 1: Add WeasyPrint and verify native rendering

**Files:**
- Modify: `engine/pyproject.toml` (dependencies list)
- Test: `engine/tests/test_bookexport.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces: a working `weasyprint` import; establishes `weasyprint.HTML(string=..., base_url=...).write_pdf() -> bytes`.

- [ ] **Step 1: Install the native dependency**

Run (macOS, one-time):
```bash
brew install pango
```
Expected: pango + cairo/harfbuzz/fontconfig install (or "already installed").

- [ ] **Step 2: Add the Python dependency**

Edit `engine/pyproject.toml`, change the `dependencies` list to:
```toml
dependencies = [
    "typer>=0.12",
    "pyyaml>=6",
    "markdown>=3.10.2",
    "weasyprint>=63",
]
```

- [ ] **Step 3: Sync the environment**

Run:
```bash
uv sync --project engine
```
Expected: resolves and installs `weasyprint` and its Python deps.

- [ ] **Step 4: Write the failing smoke test**

Create `engine/tests/test_bookexport.py`:
```python
from weasyprint import HTML


def test_weasyprint_renders_pdf_bytes():
    pdf = HTML(string="<h1>hello</h1>").write_pdf()
    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF")
```

- [ ] **Step 5: Run it (proves the native stack works)**

Run:
```bash
uv run --project engine pytest engine/tests/test_bookexport.py::test_weasyprint_renders_pdf_bytes -v
```
Expected: PASS. (If it errors with `cannot load library 'libpango'`, Step 1 didn't take — re-run brew and `export DYLD_FALLBACK_LIBRARY_PATH=$(brew --prefix)/lib` in the shell.)

- [ ] **Step 6: Commit**

```bash
git add engine/pyproject.toml engine/uv.lock engine/tests/test_bookexport.py
git commit -m "build(engine): add weasyprint for PDF book export"
```

---

## Task 2: Bundle the display font (fail-safe)

**Files:**
- Create: `engine/src/ttrpg_engine/assets/fonts/Cinzel-Regular.ttf`, `Cinzel-Bold.ttf`
- Create: `engine/src/ttrpg_engine/bookexport.py` (font helper only)
- Test: `engine/tests/test_bookexport.py`

**Interfaces:**
- Produces: `bookexport._font_face_css() -> str` — returns `@font-face` rules with absolute file paths when the TTFs exist, else `""`.

- [ ] **Step 1: Vendor the font (OFL, one-time)**

Run:
```bash
mkdir -p engine/src/ttrpg_engine/assets/fonts
curl -sL "https://github.com/google/fonts/raw/main/ofl/cinzel/static/Cinzel-Regular.ttf" \
  -o engine/src/ttrpg_engine/assets/fonts/Cinzel-Regular.ttf
curl -sL "https://github.com/google/fonts/raw/main/ofl/cinzel/static/Cinzel-Bold.ttf" \
  -o engine/src/ttrpg_engine/assets/fonts/Cinzel-Bold.ttf
```
Expected: two `.ttf` files, each > 40 KB. Verify: `ls -la engine/src/ttrpg_engine/assets/fonts`.

- [ ] **Step 2: Write the failing test**

Add to `engine/tests/test_bookexport.py`:
```python
from ttrpg_engine import bookexport


def test_font_face_css_present_when_fonts_bundled():
    css = bookexport._font_face_css()
    assert "@font-face" in css
    assert "Cinzel" in css
```

- [ ] **Step 3: Run it, verify it fails**

Run:
```bash
uv run --project engine pytest engine/tests/test_bookexport.py::test_font_face_css_present_when_fonts_bundled -v
```
Expected: FAIL (`ModuleNotFoundError` / no `_font_face_css`).

- [ ] **Step 4: Implement the font helper**

Create `engine/src/ttrpg_engine/bookexport.py`:
```python
"""Print-book PDF export: renders designed booklet PDFs (world, classes, races,
bestiary) from a game's content via WeasyPrint. Pure read + render; no state
mutation. Images resolve fail-open — a missing file degrades to text."""

from pathlib import Path

_FONT_DIR = Path(__file__).parent / "assets" / "fonts"


def _font_face_css() -> str:
    """@font-face rules for the bundled display font, using absolute file URLs
    so WeasyPrint finds them regardless of cwd. Returns "" if the TTFs are
    absent, so the CSS font stack falls back to Georgia/serif and the build
    never fails on a missing font."""
    reg = _FONT_DIR / "Cinzel-Regular.ttf"
    bold = _FONT_DIR / "Cinzel-Bold.ttf"
    if not (reg.exists() and bold.exists()):
        return ""
    return (
        f"@font-face {{ font-family: 'Cinzel'; font-weight: 400; "
        f"src: url('file://{reg}'); }}\n"
        f"@font-face {{ font-family: 'Cinzel'; font-weight: 700; "
        f"src: url('file://{bold}'); }}\n"
    )
```

- [ ] **Step 5: Run it, verify it passes**

Run:
```bash
uv run --project engine pytest engine/tests/test_bookexport.py::test_font_face_css_present_when_fonts_bundled -v
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add engine/src/ttrpg_engine/assets/fonts engine/src/ttrpg_engine/bookexport.py engine/tests/test_bookexport.py
git commit -m "feat(engine): bundle Cinzel display font for book export"
```

---

## Task 3: Book stylesheet, page shells, and image resolver

**Files:**
- Modify: `engine/src/ttrpg_engine/bookexport.py`
- Test: `engine/tests/test_bookexport.py`

**Interfaces:**
- Consumes: `_font_face_css()` (Task 2); `export.resolve_source` (existing).
- Produces:
  - `_content_image(content_dir: Path, rel: str | None) -> str | None` — fail-open, returns `rel` iff the file exists under `content_dir`, else `None`.
  - `_cover_html(title: str, subtitle: str, cover_rel: str | None) -> str`
  - `_document(title: str, subtitle: str, cover_rel: str | None, body: str) -> str` — full HTML string.
  - `render_pdf(html: str, content_dir: Path) -> bytes` — WeasyPrint render with `base_url=content_dir` so `art/...` URLs resolve; returns PDF bytes.
  - `page_count(html: str, content_dir: Path) -> int` — for tests.

- [ ] **Step 1: Write failing tests**

Add to `engine/tests/test_bookexport.py`:
```python
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
```

- [ ] **Step 2: Run, verify fail**

Run:
```bash
uv run --project engine pytest engine/tests/test_bookexport.py -k "content_image or cover_page" -v
```
Expected: FAIL (attributes not defined).

- [ ] **Step 3: Implement stylesheet, shells, resolver, render**

Append to `engine/src/ttrpg_engine/bookexport.py`:
```python
from weasyprint import HTML

from ttrpg_engine.markdown_render import esc

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
```

- [ ] **Step 4: Run, verify pass**

Run:
```bash
uv run --project engine pytest engine/tests/test_bookexport.py -k "content_image or cover_page" -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add engine/src/ttrpg_engine/bookexport.py engine/tests/test_bookexport.py
git commit -m "feat(engine): book stylesheet, cover/page shells, fail-open image resolver"
```

---

## Task 4: Races and Bestiary section builders (art + text cards)

**Files:**
- Modify: `engine/src/ttrpg_engine/bookexport.py`
- Test: `engine/tests/test_bookexport.py`

**Interfaces:**
- Consumes: `export.resolve_source(root, game_path) -> {"g","content_dir","world_name","root"}`; `game_mod.bestiary(g) -> dict[str, dict]`; `chargen._load_race_lore(g) -> dict`; `_content_image`, `_document`, `render_pdf`.
- Produces:
  - `build_races(src: dict) -> bytes`
  - `build_bestiary(src: dict) -> bytes`
  - `_roster_card(name: str, img_rel: str | None, body_html: str) -> str`

Note on data: `g["races"]` is `{name: {description, bonuses, speed}}` (ruleset). Race **portrait** paths come from content lore `content/lore/races.yaml` (`image: art/races/<race>.png`), loaded via `chargen._load_race_lore(g)`. Bestiary entries (`game_mod.bestiary(g)`) carry `name, description, ac, hp, speed, xp, difficulty, attacks, notes, image` where `image` is e.g. `art/bestiary/orc.png`.

- [ ] **Step 1: Write failing tests**

Add to `engine/tests/test_bookexport.py`:
```python
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
```

- [ ] **Step 2: Run, verify fail**

Run:
```bash
uv run --project engine pytest engine/tests/test_bookexport.py -k "races or bestiary or roster" -v
```
Expected: FAIL.

- [ ] **Step 3: Implement the roster builders**

Append to `engine/src/ttrpg_engine/bookexport.py`:
```python
from ttrpg_engine import chargen, game as game_mod


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
```

- [ ] **Step 4: Run, verify pass**

Run:
```bash
uv run --project engine pytest engine/tests/test_bookexport.py -k "races or bestiary or roster" -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add engine/src/ttrpg_engine/bookexport.py engine/tests/test_bookexport.py
git commit -m "feat(engine): races + bestiary book sections (art+text cards)"
```

---

## Task 5: Classes section builder (text overview)

**Files:**
- Modify: `engine/src/ttrpg_engine/bookexport.py`
- Test: `engine/tests/test_bookexport.py`

**Interfaces:**
- Consumes: `g["classes"]` (`{name: {description, hit_die, starting_gear, starting_gold, skills, skill_choices, ...}}`), `g["progression"]["max_level"]`, `_content_image`, `_document`, `render_pdf`.
- Produces: `build_classes(src: dict) -> bytes`.

- [ ] **Step 1: Write failing test**

Add to `engine/tests/test_bookexport.py`:
```python
def test_build_classes_pdf():
    pdf = bookexport.build_classes(_familyrpg_src())
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 5000
```

- [ ] **Step 2: Run, verify fail**

Run:
```bash
uv run --project engine pytest engine/tests/test_bookexport.py::test_build_classes_pdf -v
```
Expected: FAIL.

- [ ] **Step 3: Implement**

Append to `engine/src/ttrpg_engine/bookexport.py`:
```python
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
```

- [ ] **Step 4: Run, verify pass**

Run:
```bash
uv run --project engine pytest engine/tests/test_bookexport.py::test_build_classes_pdf -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add engine/src/ttrpg_engine/bookexport.py engine/tests/test_bookexport.py
git commit -m "feat(engine): classes book section (text overview)"
```

---

## Task 6: World section builder (SVG map + lore + full-page painted map)

**Files:**
- Modify: `engine/src/ttrpg_engine/bookexport.py`
- Test: `engine/tests/test_bookexport.py`

**Interfaces:**
- Consumes: `content_dir/maps/world-map.svg` (inline SVG, smaller, at top), `content_dir/setting.md`/`history.md` (lore, if present; else fall back to `content/lore/*.yaml` presence-agnostic — render "No world lore authored yet." when none), `content_dir/maps/WorldMapPainted.png` (full-page), `render_markdown` from `markdown_render`.
- Produces: `build_world(src: dict) -> bytes`.

Note: familyrpg currently has **no** `setting.md`/`history.md`; it has `content/lore/{locations.yaml,races.yaml}` and `content/maps/{world-map.svg, WorldMapPainted.png, region.yaml}`. The builder must render a valid PDF regardless — lore is a stub the operator fleshes out over time (per spec). SVG is inlined (not `<img>`) so WeasyPrint renders it crisply.

- [ ] **Step 1: Write failing test**

Add to `engine/tests/test_bookexport.py`:
```python
def test_build_world_pdf():
    pdf = bookexport.build_world(_familyrpg_src())
    assert pdf.startswith(b"%PDF")
    # cover + lore page + full-page painted map = at least 3 pages
    src = _familyrpg_src()
    html = bookexport._world_html(src)
    assert bookexport.page_count(html, src["content_dir"]) >= 3
```

- [ ] **Step 2: Run, verify fail**

Run:
```bash
uv run --project engine pytest engine/tests/test_bookexport.py::test_build_world_pdf -v
```
Expected: FAIL.

- [ ] **Step 3: Implement**

Append to `engine/src/ttrpg_engine/bookexport.py`:
```python
from ttrpg_engine.markdown_render import render_markdown as _md


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
```

- [ ] **Step 4: Run, verify pass**

Run:
```bash
uv run --project engine pytest engine/tests/test_bookexport.py::test_build_world_pdf -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add engine/src/ttrpg_engine/bookexport.py engine/tests/test_bookexport.py
git commit -m "feat(engine): world book section (svg map + lore + painted map)"
```

---

## Task 7: CLI wiring — `engine export book <section>`

**Files:**
- Modify: `engine/src/ttrpg_engine/cli.py` (import `bookexport`; add subcommand near the existing `export_app`, lines ~685-732)
- Modify: `engine/src/ttrpg_engine/bookexport.py` (add `SECTIONS` registry)
- Test: `engine/tests/test_bookexport.py`

**Interfaces:**
- Consumes: existing `require_root`, `guard`, `emit`, `export_mod.resolve_source`, `export_app` in `cli.py`.
- Produces:
  - `bookexport.SECTIONS: dict[str, tuple[callable, str]]` = `{"world": (build_world, "world.pdf"), "classes": (build_classes, "classes.pdf"), "races": (build_races, "races.pdf"), "bestiary": (build_bestiary, "bestiary.pdf")}`.
  - CLI: `engine export book <section|all> [--out exports] [--game PATH]` writing `<out>/<section>.pdf` and emitting `{"file": "<path>"}` per file.

- [ ] **Step 1: Add the registry + failing test**

Append to `engine/src/ttrpg_engine/bookexport.py`:
```python
SECTIONS = {
    "world": (build_world, "world.pdf"),
    "classes": (build_classes, "classes.pdf"),
    "races": (build_races, "races.pdf"),
    "bestiary": (build_bestiary, "bestiary.pdf"),
}
```

Add to `engine/tests/test_bookexport.py`:
```python
def test_sections_registry_covers_all_four():
    assert set(bookexport.SECTIONS) == {"world", "classes", "races", "bestiary"}
    for _name, (builder, filename) in bookexport.SECTIONS.items():
        assert callable(builder)
        assert filename.endswith(".pdf")
```

- [ ] **Step 2: Run, verify pass on registry (implementation is trivial data)**

Run:
```bash
uv run --project engine pytest engine/tests/test_bookexport.py::test_sections_registry_covers_all_four -v
```
Expected: PASS.

- [ ] **Step 3: Write the CLI end-to-end test**

Add to `engine/tests/test_bookexport.py`:
```python
import subprocess, sys


def test_cli_export_book_all_writes_pdfs(tmp_path):
    out = tmp_path / "exports"
    r = subprocess.run(
        [sys.executable, "-m", "ttrpg_engine.cli", "export", "book", "all",
         "--game", "games/familyrpg", "--out", str(out)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    for fn in ("world.pdf", "classes.pdf", "races.pdf", "bestiary.pdf"):
        assert (out / fn).exists(), fn
        assert (out / fn).read_bytes().startswith(b"%PDF")
```
(If `python -m ttrpg_engine.cli` isn't wired, use the installed script: replace the command with `["engine", "export", "book", "all", ...]` — Typer's `app` is the console entry.)

- [ ] **Step 4: Run, verify it fails**

Run:
```bash
uv run --project engine pytest engine/tests/test_bookexport.py::test_cli_export_book_all_writes_pdfs -v
```
Expected: FAIL (`No such command 'book'`).

- [ ] **Step 5: Wire the CLI**

In `engine/src/ttrpg_engine/cli.py`: add `bookexport` to the existing multi-import on line 9 (append `, bookexport`), then add after the `export_campaign_cmd` function (after ~line 732):
```python
@export_app.command("book")
def export_book_cmd(
    section: str = typer.Argument(..., help="world | classes | races | bestiary | all"),
    out: Path = typer.Option(Path("exports"), "--out", help="Output directory."),
    game: Path | None = typer.Option(None, "--game", help="Game repo path (repo-side, no world needed)."),
):
    names = list(bookexport.SECTIONS) if section == "all" else [section]
    unknown = [n for n in names if n not in bookexport.SECTIONS]
    if unknown:
        raise typer.BadParameter(f"unknown section(s): {', '.join(unknown)}")
    root = None if game is not None else require_root()
    src = guard(export_mod.resolve_source, root, game)
    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        builder, filename = bookexport.SECTIONS[name]
        pdf = guard(builder, src)
        path = (out_dir / filename).resolve()
        path.write_bytes(pdf)
        emit({"file": str(path)})
```

- [ ] **Step 6: Run, verify pass**

Run:
```bash
uv run --project engine pytest engine/tests/test_bookexport.py::test_cli_export_book_all_writes_pdfs -v
```
Expected: PASS. If the `python -m` form errored, switch the test to the `engine` console script per Step 3's note and re-run.

- [ ] **Step 7: Run the full test file**

Run:
```bash
uv run --project engine pytest engine/tests/test_bookexport.py -v
```
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add engine/src/ttrpg_engine/cli.py engine/src/ttrpg_engine/bookexport.py engine/tests/test_bookexport.py
git commit -m "feat(engine): engine export book <section|all> CLI"
```

---

## Task 8: Replace the Google Docs skill with an export-pdf skill

**Files:**
- Create: `.claude/skills/export-pdf/SKILL.md`
- Delete: `.claude/skills/export-docs/SKILL.md` (and its directory)
- Check: grep the repo for other `gws`/Google-Docs references and remove any that only served the old path.

**Interfaces:** none (docs/skill only).

- [ ] **Step 1: Confirm no engine code depends on gws**

Run:
```bash
grep -rn "gws\|google-apps\|webViewLink" engine .claude/skills | grep -v export-docs
```
Expected: no engine hits (the gws path lived only in the old skill).

- [ ] **Step 2: Write the new skill**

Create `.claude/skills/export-pdf/SKILL.md`:
```markdown
---
name: export-pdf
description: Use when the operator wants printable/shareable PDF booklets of the game — World, Classes, Races, and Bestiary — as designed print books.
---

# Export print-book PDFs

Renders four designed booklet PDFs from committed content and committed cover
art. Deterministic and offline: no API calls at build time.

## Prerequisite (one-time)

WeasyPrint needs Pango. On macOS: `brew install pango`. If a render dies with
`cannot load library 'libpango'`, that's the missing dep.

## 1. Build the PDFs

Inside a world (uses `canon/` + the world's pinned game):

    engine export book all

Repo-side (uses a game's own `content/` + ruleset):

    engine export book all --game games/familyrpg

Or one at a time: `engine export book bestiary --game games/familyrpg`.
Default output dir is `./exports/`; pass `--out DIR` to change it. Each file
emits `{"file": "<path>.pdf"}`.

## 2. Cover art (optional, one-time, costs BFL spend)

Each booklet shows a full-page cover banner from
`content/art/covers/{world,classes,races,bestiary}.png`. If a cover is
missing the build still succeeds with a text-only cover page. To generate the
banners, use the **image-gen** skill with prompts drawn from real in-game
content (e.g. the Bestiary cover = actual game creatures in a clash), write
them to `games/<game>/content/art/covers/`, and commit. These assets are
shared with the web UI.

## 3. Report

Report the four local PDF paths from step 1. There is no upload step — the PDF
is the deliverable.
```

- [ ] **Step 3: Remove the old skill**

Run:
```bash
git rm -r .claude/skills/export-docs
```

- [ ] **Step 4: Verify the new skill lints (frontmatter present)**

Run:
```bash
head -5 .claude/skills/export-pdf/SKILL.md
```
Expected: valid `---` frontmatter with `name: export-pdf`.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/export-pdf/SKILL.md
git commit -m "docs(skill): replace export-docs (Google Docs) with export-pdf"
```

---

## Task 9: Generate and commit the four cover banners (Stage A — spend, not unit-tested)

**Files:**
- Create: `games/familyrpg/content/art/covers/{world,classes,races,bestiary}.png`

**This task costs real BFL API spend and is non-deterministic — it is NOT part of the automated test loop.** It is run once by the operator (or with explicit approval) via the image-gen skill. The build already works without it (fail-open text covers), so this can happen anytime.

- [ ] **Step 1: Draft prompts from real content**

Prompts, grounded in actual familyrpg content (fantasy book-cover art, bold dramatic composition, no text baked in — the title is overlaid by the layout):
- **world**: "A sweeping fantasy world map vista — the Known World: great plains, white cliffs, a dragon isle on the horizon, painterly, warm parchment tones."
- **classes**: "A heroic fantasy adventuring party of mixed classes — a warrior, a mage mid-cast, a ranger — dramatic hero lighting, painterly."
- **races**: "A gathering of diverse fantasy peoples together — dwarf, elf, dragonborn, halfling, goliath — group portrait, painterly, warm."
- **bestiary**: "A clash of fantasy monsters — a young dragon, a troll, and an owlbear mid-brawl in a rocky pass — dynamic action, dramatic, painterly."

- [ ] **Step 2: Generate via the image-gen skill**

Invoke the **image-gen** skill (Skill tool) with the four prompts, model `flux-2-klein-4b` (matches existing race/bestiary portraits), writing each to `games/familyrpg/content/art/covers/<name>.png`. Respect `IMAGEGEN_MAX_PER_RUN` / spend caps. Example single call:
```bash
source exports.sh && uv run tools/imagegen.py \
  --prompt "<bestiary prompt above>" \
  --out games/familyrpg/content/art/covers/bestiary.png \
  --model flux-2-klein-4b
```

- [ ] **Step 3: Rebuild and eyeball the covers**

Run:
```bash
engine export book all --game games/familyrpg
open exports/bestiary.pdf
```
Expected: each PDF opens with its cover banner on page 1, title overlaid.

- [ ] **Step 4: Commit**

```bash
git add games/familyrpg/content/art/covers
git commit -m "content(familyrpg): cover banners for the four export booklets"
```

---

## Self-Review Notes

- **Spec coverage:** four booklets (Tasks 4–6), covers fail-open (Task 3/9), WeasyPrint engine (Task 1), shared art location under `content/art/` (Tasks 4/9), CLI (Task 7), Google-Docs removal (Task 8), two-stage split (build in 1–7, assets in 9), font reproducibility (Task 2), no-index (templates omit TOC). All covered.
- **Determinism:** build tasks are offline and re-runnable; only Task 9 spends/varies.
- **Fail-open:** every image (cover, portrait, painted map, svg) degrades to text/omission — no image is required.
- **Types:** `resolve_source` return keys (`g`, `content_dir`, `world_name`, `root`), `SECTIONS` shape, and builder signatures `(src) -> bytes` are consistent across Tasks 3–7.
