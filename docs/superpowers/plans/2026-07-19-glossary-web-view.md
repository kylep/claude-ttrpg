# Glossary Web View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an in-window "Glossary" overlay to the world viewer showing the four booklets (World, Classes, Races, Bestiary) with sidebar nav, lens-aware content, and app-native rendering — reusing the content `bookexport` builds for the PDFs.

**Architecture:** Split `bookexport`'s section content-building from PDF rendering so the PDF and web paths share one source. Expose `glossary_manifest(src)` and `glossary_section(src, name, lens)`; serve them from two new `serve.py` routes; render them in a `viewer.html` overlay styled with the viewer's own theme. Bestiary is the only lens-sensitive section (player lens hides AC/HP/XP/attacks).

**Tech Stack:** Python 3.11+, stdlib `http.server`, Typer CLI, vanilla-JS SPA (`viewer.html`), WeasyPrint (unchanged PDF path).

## Global Constraints

- Python >=3.11. Tests: `uv run --project engine pytest` (baseline 394 passing — no regressions).
- Lens derived from `?lens=`: `gm` → "gm", anything else → "player" (match existing routes in `serve.py`).
- Player-lens Bestiary shows name + art + description ONLY; GM-only fields (AC, HP, Speed, XP, difficulty, attacks, notes) are omitted. All creatures still appear. Classes, Races, World render fully in both lenses.
- PDF export path is unchanged and always full (`lens="gm"`). `build_world/classes/races/bestiary` must still emit valid PDFs.
- All author text escaped via `esc` (already done in the current builders — preserve it verbatim when extracting).
- Section titles exactly: World→"The World", Classes→"Classes", Races→"Races", Bestiary→"Bestiary". Sidebar order: world, classes, races, bestiary.
- Content-relative art paths (`art/...`) only — no absolute paths; they resolve in the browser against the existing `/art/` route.
- Viewer CSS tokens to reuse: `--ink #171412, --surface #211d19, --edge #383028, --parchment #e8e0d2, --muted #9c917f, --ember #d9973b, --blood #b8453c, --moss #7d9b5e, --gold #c9a86a, --serif, --mono`. `LENS` and `el(tag,cls,text)` already exist in viewer.html.

---

## File Structure

- **Modify** `engine/src/ttrpg_engine/bookexport.py` — extract body builders, add lens + glossary helpers (Task 1).
- **Modify** `engine/tests/test_bookexport.py` — lens/glossary unit tests (Task 1).
- **Modify** `engine/src/ttrpg_engine/serve.py` — two routes + imports (Task 2).
- **Modify** `engine/tests/test_serve.py` — glossary route test (Task 2).
- **Modify** `engine/src/ttrpg_engine/viewer.html` — button, overlay, nav, fetch, screen CSS (Task 3).

---

## Task 1: Split content builders + lens + glossary helpers in bookexport

**Files:**
- Modify: `engine/src/ttrpg_engine/bookexport.py:136-247` (the four `build_*` + `_world_html`, and append helpers)
- Test: `engine/tests/test_bookexport.py`

**Interfaces:**
- Consumes: existing `_content_image`, `_roster_card`, `_document`, `render_pdf`, `_title_case`, `esc`, `chargen._load_race_lore`, `game_mod.bestiary`, `_world_lore_html`, `_world_svg_html`.
- Produces:
  - `_races_body(src) -> str`, `_classes_body(src) -> str`, `_world_body(src) -> str`
  - `_bestiary_body(src, lens="gm") -> str`
  - `GLOSSARY_TITLES: dict[str,str]`
  - `glossary_manifest(src) -> list[dict]` with keys `id`,`title`,`cover`
  - `glossary_section(src, name, lens="player") -> dict` with keys `id`,`title`,`cover`,`body_html`; raises `KeyError` on unknown name
  - `build_races/classes/bestiary/world(src) -> bytes` unchanged externally.

- [ ] **Step 1: Write the failing tests**

Add to `engine/tests/test_bookexport.py`:
```python
def test_bestiary_body_lens_hides_stats_for_player():
    src = _familyrpg_src()
    gm = bookexport._bestiary_body(src, "gm")
    player = bookexport._bestiary_body(src, "player")
    assert "AC " in gm and "HP " in gm and "Attacks:" in gm
    assert "AC " not in player and "HP " not in player and "Attacks:" not in player
    # creatures still listed for players (names present)
    assert "Adult Dragon" in player


def test_glossary_manifest_four_sections():
    m = bookexport.glossary_manifest(_familyrpg_src())
    assert [s["id"] for s in m] == ["world", "classes", "races", "bestiary"]
    assert [s["title"] for s in m] == ["The World", "Classes", "Races", "Bestiary"]
    # familyrpg has cover art committed → resolves (not None)
    assert all(s["cover"] for s in m)


def test_glossary_section_returns_body_and_raises_unknown():
    src = _familyrpg_src()
    sec = bookexport.glossary_section(src, "races", "player")
    assert sec["id"] == "races" and sec["title"] == "Races"
    assert "<div class='roster'>" in sec["body_html"]
    import pytest
    with pytest.raises(KeyError):
        bookexport.glossary_section(src, "bogus", "player")


def test_builds_still_emit_pdfs_after_refactor():
    src = _familyrpg_src()
    for b in (bookexport.build_world, bookexport.build_classes,
              bookexport.build_races, bookexport.build_bestiary):
        assert b(src).startswith(b"%PDF")
```

- [ ] **Step 2: Run, verify they fail**

Run: `uv run --project engine pytest engine/tests/test_bookexport.py -k "lens or glossary or after_refactor" -v`
Expected: FAIL (helpers not defined).

- [ ] **Step 3: Refactor — replace `build_races`,`build_bestiary`,`build_classes` and split `_world_html`**

In `engine/src/ttrpg_engine/bookexport.py`, replace the bodies of `build_races` (lines ~136-156), `build_bestiary` (~159-180), `build_classes` (~183-200) and `_world_html`/`build_world` (~223-237) with the following. Extract the content into `_*_body` helpers and keep `build_*` as thin PDF wrappers:
```python
def _races_body(src):
    g, content_dir = src["g"], src["content_dir"]
    lore = chargen._load_race_lore(g)
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
            f"<span class='tag'>Speed {esc(str(race['speed']))}</span></p>"
        )
        cards.append(_roster_card(name.title(), img, body))
    return f"<div class='roster'>{''.join(cards)}</div>"


def build_races(src):
    body = _races_body(src)
    cover = _content_image(src["content_dir"], "art/covers/races.png")
    html = _document("Races", src["world_name"] or src["g"]["meta"]["name"].title(), cover, body)
    return render_pdf(html, src["content_dir"])


def _bestiary_body(src, lens="gm"):
    g, content_dir = src["g"], src["content_dir"]
    full = lens == "gm"
    cards = []
    for mid, mon in sorted(game_mod.bestiary(g).items()):
        img = _content_image(content_dir, mon.get("image"))
        body = f"<p>{esc(mon.get('description', ''))}</p>"
        if full:
            attacks = "; ".join(
                f"{a['name']} (+{a['attack_mod']}, {a['damage']}, range {a['range']})"
                for a in mon.get("attacks", [])
            ) or "—"
            notes = f"<p><strong>Notes:</strong> {esc(mon['notes'].strip())}</p>" if mon.get("notes") else ""
            body += (
                f"<p><span class='tag'>AC {esc(str(mon['ac']))}</span><span class='tag'>HP {esc(str(mon['hp']))}</span>"
                f"<span class='tag'>Speed {esc(str(mon['speed']))}</span><span class='tag'>XP {esc(str(mon['xp']))}</span>"
                f"<span class='tag'>{esc(mon.get('difficulty', '?'))}</span></p>"
                f"<p><strong>Attacks:</strong> {esc(attacks)}</p>{notes}"
            )
        cards.append(_roster_card(mon.get("name", mid.title()), img, body))
    return f"<div class='roster'>{''.join(cards)}</div>"


def build_bestiary(src):
    body = _bestiary_body(src, "gm")
    cover = _content_image(src["content_dir"], "art/covers/bestiary.png")
    html = _document("Bestiary", src["world_name"] or src["g"]["meta"]["name"].title(), cover, body)
    return render_pdf(html, src["content_dir"])


def _classes_body(src):
    g = src["g"]
    cards = []
    for name, cls in sorted(g["classes"].items()):
        gear = ", ".join(_title_case(i) for i in cls.get("starting_gear", [])) or "—"
        skills = ", ".join(_title_case(s) for s in cls.get("skills", []))
        cards.append(
            f"<div class='card'><h3>{esc(name.title())}</h3>"
            f"<p class='lead'>{esc(cls.get('description', '').strip())}</p>"
            f"<p><span class='tag'>Hit die d{esc(str(cls['hit_die']))}</span>"
            f"<span class='tag'>Start gold {esc(str(cls.get('starting_gold', 0)))} gp</span></p>"
            f"<p><strong>Starting gear:</strong> {esc(gear)}.</p>"
            f"<p><strong>Skills:</strong> choose {cls.get('skill_choices', 0)} from {esc(skills)}.</p>"
            f"</div>"
        )
    return "".join(cards)


def build_classes(src):
    body = _classes_body(src)
    cover = _content_image(src["content_dir"], "art/covers/classes.png")
    html = _document("Classes", src["world_name"] or src["g"]["meta"]["name"].title(), cover, body)
    return render_pdf(html, src["content_dir"])


def _world_body(src):
    content_dir = src["content_dir"]
    svg = _world_svg_html(content_dir)
    lore = _world_lore_html(content_dir)
    body = f"{svg}{lore}"
    painted = _content_image(content_dir, "maps/WorldMapPainted.png")
    if painted:
        body += f"<div class='fullbleed'><img src='{esc(painted)}' alt='World map'></div>"
    return body


def _world_html(src):
    cover = _content_image(src["content_dir"], "art/covers/world.png")
    return _document("The World", src["world_name"] or src["g"]["meta"]["name"].title(),
                     cover, _world_body(src))


def build_world(src):
    return render_pdf(_world_html(src), src["content_dir"])
```
Leave `_world_lore_html` and `_world_svg_html` exactly as they are. Keep the `SECTIONS` dict (below `build_world`) unchanged.

- [ ] **Step 4: Append the glossary helpers** (after the `SECTIONS` dict)
```python
GLOSSARY_TITLES = {
    "world": "The World",
    "classes": "Classes",
    "races": "Races",
    "bestiary": "Bestiary",
}

_GLOSSARY_BODIES = {
    "world": lambda src, lens: _world_body(src),
    "classes": lambda src, lens: _classes_body(src),
    "races": lambda src, lens: _races_body(src),
    "bestiary": lambda src, lens: _bestiary_body(src, lens),
}


def glossary_manifest(src):
    """The four glossary sections with titles and fail-open cover paths."""
    content_dir = src["content_dir"]
    return [
        {"id": sid, "title": title,
         "cover": _content_image(content_dir, f"art/covers/{sid}.png")}
        for sid, title in GLOSSARY_TITLES.items()
    ]


def glossary_section(src, name, lens="player"):
    """One section's rendered content for the web glossary. Raises KeyError on
    an unknown section name (the caller maps that to a 404)."""
    if name not in _GLOSSARY_BODIES:
        raise KeyError(name)
    return {
        "id": name,
        "title": GLOSSARY_TITLES[name],
        "cover": _content_image(src["content_dir"], f"art/covers/{name}.png"),
        "body_html": _GLOSSARY_BODIES[name](src, lens),
    }
```

- [ ] **Step 5: Run the tests, verify pass**

Run: `uv run --project engine pytest engine/tests/test_bookexport.py -v`
Expected: all PASS (new + existing, incl. the PDF regression test).

- [ ] **Step 6: Commit**
```bash
git add engine/src/ttrpg_engine/bookexport.py engine/tests/test_bookexport.py
git commit -m "refactor(engine): split book content from PDF; add lens-aware glossary helpers"
```

---

## Task 2: Serve glossary routes

**Files:**
- Modify: `engine/src/ttrpg_engine/serve.py` (imports near top; two routes inside `do_GET`, before the final `else`)
- Test: `engine/tests/test_serve.py`

**Interfaces:**
- Consumes: `bookexport.glossary_manifest`, `bookexport.glossary_section`, `export_mod.resolve_source`, existing `self.root`, `self._json`, `query`.
- Produces routes: `GET /api/glossary` → manifest JSON; `GET /api/glossary/<section>[?lens=]` → section JSON or 404.

- [ ] **Step 1: Write the failing test**

Add to `engine/tests/test_serve.py`:
```python
def test_glossary_manifest_and_lens(live):
    _, port = live
    status, body = _get(port, "/api/glossary")
    assert status == 200
    manifest = json.loads(body)
    assert [s["id"] for s in manifest] == ["world", "classes", "races", "bestiary"]

    sp, pbody = _get(port, "/api/glossary/bestiary?lens=player")
    sg, gbody = _get(port, "/api/glossary/bestiary?lens=gm")
    assert sp == 200 and sg == 200
    player = json.loads(pbody)
    gm = json.loads(gbody)
    assert "HP " in gm["body_html"]
    assert "HP " not in player["body_html"]

    sx, _xb = _get(port, "/api/glossary/bogus")
    assert sx == 404
```
(The `live`/`wroot` fixture builds a world from the minigame fixture, whose bestiary includes goblins with HP — so the GM body contains "HP " and the player body does not.)

- [ ] **Step 2: Run, verify it fails**

Run: `uv run --project engine pytest engine/tests/test_serve.py::test_glossary_manifest_and_lens -v`
Expected: FAIL (404 on `/api/glossary`).

- [ ] **Step 3: Add imports** — extend the `from ttrpg_engine import ...` line(s) at the top of `serve.py` so it imports `bookexport` and `export as export_mod` (add them to the existing import; do not duplicate a line).

- [ ] **Step 4: Add the routes** inside `do_GET`, immediately before the final `else:` (the `{"error": "not found"}` branch):
```python
            elif path == "/api/glossary":
                src = export_mod.resolve_source(self.root, None)
                self._json(bookexport.glossary_manifest(src))
            elif path.startswith("/api/glossary/"):
                name = path.removeprefix("/api/glossary/")
                lens = "gm" if query.get("lens", ["player"])[0] == "gm" else "player"
                src = export_mod.resolve_source(self.root, None)
                try:
                    self._json(bookexport.glossary_section(src, name, lens))
                except KeyError:
                    self._json({"error": "not found"}, 404)
```

- [ ] **Step 5: Run, verify pass**

Run: `uv run --project engine pytest engine/tests/test_serve.py -v`
Expected: all PASS (new test + existing serve tests).

- [ ] **Step 6: Commit**
```bash
git add engine/src/ttrpg_engine/serve.py engine/tests/test_serve.py
git commit -m "feat(engine): /api/glossary manifest + section routes (lens-aware)"
```

---

## Task 3: Glossary button, overlay, and rendering in viewer.html

**Files:**
- Modify: `engine/src/ttrpg_engine/viewer.html` (CSS block; header markup ~line 280-285; a new overlay div near `#overlay` ~line 307; JS near the entity-overlay JS ~line 542-552)

**Interfaces:**
- Consumes: `LENS` const, `el(tag,cls,text)` helper, existing `/api/glossary` routes, `/art/` static route.
- Produces: a `#gloss` overlay opened by `#gloss-btn`; no new global names leak beyond `openGlossary`/`closeGlossary`.

This task is UI. Follow the viewer's existing aesthetic — reuse the CSS tokens in Global Constraints; match the look of the entity-sheet overlay (`#overlay`) and the aside `.card`s. Consider superpowers:frontend-design for polish, but stay within the existing theme (do not introduce a new palette or font).

- [ ] **Step 1: Add the header button.** In the `<header>` block (~line 280), add a button after the `lens` span:
```html
  <button id="gloss-btn" type="button">Glossary</button>
```

- [ ] **Step 2: Add the overlay container** next to the existing `#overlay` (~line 307):
```html
<div id="gloss" hidden role="dialog" aria-modal="true" aria-label="Glossary"></div>
```

- [ ] **Step 3: Add CSS** in the `<style>` block (place near the `#overlay` rules ~line 160). Scope everything under `.glossary` so bookexport's `.card`/`.tag`/`.roster` class names don't collide with the viewer's aside `.card`:
```css
  header #gloss-btn {
    margin-left: auto; font-family: var(--mono); font-size: .72rem;
    color: var(--gold); background: transparent; border: 1px solid var(--gold);
    border-radius: 4px; padding: .2rem .7rem; cursor: pointer; letter-spacing: .04em;
  }
  header #gloss-btn:hover { background: var(--gold); color: var(--ink); }
  #gloss { position: fixed; inset: 0; background: rgba(12, 9, 7, .96); z-index: 5;
    display: grid; grid-template-columns: 210px minmax(0, 1fr); overflow: hidden; }
  #gloss[hidden] { display: none; }
  .gl-side { border-right: 1px solid var(--edge); padding: 1rem .6rem; overflow-y: auto;
    display: flex; flex-direction: column; gap: .3rem; background: var(--surface); }
  .gl-side .gl-title { font-family: var(--mono); font-size: .7rem; color: var(--muted);
    letter-spacing: .12em; margin: 0 .5rem .6rem; }
  .gl-side button { text-align: left; background: transparent; border: 0; cursor: pointer;
    color: var(--parchment); font-family: var(--serif); font-size: 1rem;
    padding: .45rem .6rem; border-radius: 5px; }
  .gl-side button:hover { background: var(--edge); }
  .gl-side button.active { background: var(--edge); color: var(--gold); }
  .gl-side .gl-close { margin-top: auto; color: var(--muted); font-family: var(--mono);
    font-size: .72rem; }
  .glossary { overflow-y: auto; padding: 0 0 3rem; }
  .glossary .gl-banner { width: 100%; max-height: 320px; object-fit: cover; display: block; }
  .glossary .gl-head { padding: 1.2rem 2rem .2rem; }
  .glossary h1 { font-family: var(--serif); font-size: 2rem; color: var(--gold); margin: 0; }
  .glossary .gl-body { padding: 1rem 2rem; max-width: 860px; }
  .glossary h3 { font-family: var(--serif); color: var(--ember); margin: 0 0 .3rem; }
  .glossary .card { border: 1px solid var(--edge); border-radius: 8px; background: var(--surface);
    padding: 1rem 1.2rem; margin: 1rem 0; overflow: hidden; }
  .glossary .roster img.portrait { float: left; width: 120px; height: 120px; object-fit: cover;
    border-radius: 6px; border: 1px solid var(--edge); margin: 0 1rem .5rem 0; }
  .glossary .tag { display: inline-block; background: var(--edge); color: var(--parchment);
    border-radius: 4px; padding: .1rem .55rem; font-size: .78rem; font-family: var(--mono);
    margin: 0 .3rem .3rem 0; }
  .glossary .lead { margin: .4rem 0; }
  .glossary .fullbleed { text-align: center; margin: 1.4rem 0; }
  .glossary .fullbleed img { max-width: 100%; border-radius: 8px; }
  .glossary svg { max-width: 100%; height: auto; }
  @media (max-width: 720px) {
    #gloss { grid-template-columns: 1fr; grid-template-rows: auto minmax(0, 1fr); }
    .gl-side { flex-direction: row; flex-wrap: wrap; border-right: 0; border-bottom: 1px solid var(--edge); }
    .gl-side .gl-title { width: 100%; }
  }
```
(Note: the constrained `max-width:120mm` inline style on the world SVG wrapper from bookexport is harmless on screen; `.glossary svg { max-width:100% }` keeps it responsive.)

- [ ] **Step 4: Add the JS** near the entity-overlay JS (~line 542-552):
```javascript
const glossEl = document.getElementById("gloss");
let glossLoaded = false;

async function loadGlossSection(id, sideButtons) {
  sideButtons.forEach(b => b.classList.toggle("active", b.dataset.id === id));
  const r = await fetch("/api/glossary/" + encodeURIComponent(id) + "?lens=" + LENS);
  const content = glossEl.querySelector(".glossary");
  content.replaceChildren();
  if (!r.ok) { content.append(el("p", "gl-body", "Could not load this section.")); return; }
  const sec = await r.json();
  if (sec.cover) {
    const img = el("img", "gl-banner"); img.src = sec.cover; img.alt = ""; content.append(img);
  }
  const head = el("div", "gl-head"); head.append(el("h1", null, sec.title)); content.append(head);
  const bodyWrap = el("div", "gl-body");
  bodyWrap.innerHTML = sec.body_html;   // server-escaped content (see spec: trust model)
  content.append(bodyWrap);
  content.scrollTop = 0;
}

async function openGlossary() {
  const r = await fetch("/api/glossary");
  const manifest = r.ok ? await r.json() : [];
  const side = el("nav", "gl-side");
  side.append(el("div", "gl-title", "GLOSSARY"));
  const buttons = manifest.map(sec => {
    const b = el("button", null, sec.title); b.dataset.id = sec.id;
    b.addEventListener("click", () => loadGlossSection(sec.id, buttons));
    side.append(b); return b;
  });
  const close = el("button", "gl-close", "✕ Close"); close.addEventListener("click", closeGlossary);
  side.append(close);
  const content = el("div", "glossary");
  glossEl.replaceChildren(side, content);
  glossEl.hidden = false;
  if (manifest.length) loadGlossSection(manifest[0].id, buttons);
}

function closeGlossary() { glossEl.hidden = true; glossEl.replaceChildren(); }

document.getElementById("gloss-btn").addEventListener("click", openGlossary);
glossEl.addEventListener("click", e => { if (e.target === glossEl) closeGlossary(); });
document.addEventListener("keydown", e => { if (e.key === "Escape" && !glossEl.hidden) closeGlossary(); });
```
(The existing Escape handler for `#overlay` still runs; guarding on `!glossEl.hidden` keeps the two overlays independent. `glossLoaded` is reserved for future caching — leave it declared and unused is NOT acceptable; if you don't use it, delete the `let glossLoaded` line.)

- [ ] **Step 5: Manual smoke via the CLI-rendered HTML.** There is no JS test harness in this repo; verify by loading the page markup for syntax and by the controller's live check (next). At minimum run:
```bash
uv run --project engine python -c "import pathlib; html=pathlib.Path('engine/src/ttrpg_engine/viewer.html').read_text(); assert 'gloss-btn' in html and 'openGlossary' in html and '.glossary .card' in html; print('viewer markup OK')"
```
Expected: `viewer markup OK`.

- [ ] **Step 6: Commit**
```bash
git add engine/src/ttrpg_engine/viewer.html
git commit -m "feat(viewer): in-window Glossary overlay with sidebar nav (lens-aware)"
```

---

## Task 4: Live verification (controller)

Not a code task — the controller runs this after Task 3 to confirm the feature works end to end.

- [ ] Build a throwaway world from `games/familyrpg`, `engine serve` on an ephemeral port in the background, then:
  - `curl -s localhost:PORT/api/glossary` → 4 sections with cover paths.
  - `curl -s "localhost:PORT/api/glossary/bestiary?lens=player"` vs `?lens=gm` → confirm the player body lacks `HP ` / `Attacks:` and the GM body has them.
  - `curl -s "localhost:PORT/api/glossary/world?lens=player"` → body contains the inline `<svg` and the painted-map `<img`.
  - If a headless browser (`chrome --headless --screenshot`) is available, screenshot `/` with the overlay open and eyeball the rendering; otherwise rely on the API checks + code review.
- [ ] Full suite green: `uv run --project engine pytest -q` (>=394 + new tests, no regressions).

---

## Self-Review Notes

- **Spec coverage:** content split (T1), lens-aware bestiary (T1), manifest+section API (T1/T2), routes (T2), button+overlay+nav+screen CSS (T3), images via existing `/art/` (no new route), PDF path unchanged (T1 regression test), live verify (T4). All covered.
- **Trust:** `body_html` inserted via `innerHTML` is server-escaped (`esc`/`render_markdown`) with first-party inline SVG — documented in the spec, consistent with the exporter.
- **No collisions:** glossary content styled only under `.glossary`; the viewer's aside `.card` is untouched.
- **Types:** `glossary_manifest` → list of `{id,title,cover}`; `glossary_section` → `{id,title,cover,body_html}`, raises KeyError on unknown; consumed consistently by serve.py (KeyError→404) and viewer.js.
