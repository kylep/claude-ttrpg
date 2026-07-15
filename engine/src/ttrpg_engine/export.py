"""Printable-docs export: renders self-contained, print-friendly HTML books
from a game definition (ruleset + content) or a world's canon. No mutation
of state; pure read + render."""

from pathlib import Path

import yaml

from ttrpg_engine import game as game_mod
from ttrpg_engine import quests as quests_mod
from ttrpg_engine import worldfs
from ttrpg_engine.errors import EngineError
from ttrpg_engine.markdown_render import esc, render_markdown as _md


def _title_case(tag: str) -> str:
    return tag.replace("_", " ").title()


# --- source resolution -------------------------------------------------------

def resolve_source(root: Path | None, game_path: Path | None) -> dict:
    """Resolve where content and ruleset come from.

    --game PATH (repo-side): ruleset + content come straight from the game
    directory; there is no world, so `root` and `world_name` are None.

    Inside a world (root given): content comes from canon/ (the world's own
    truth), the ruleset from the world's pinned game. `root` is kept so
    campaign export can pull the live quest list.
    """
    if game_path is not None:
        game_path = Path(game_path)
        errors = game_mod.validate(game_path)
        if errors:
            raise EngineError("game_invalid", "; ".join(errors))
        g = game_mod.load(game_path)
        return {"g": g, "content_dir": g["content_dir"], "world_name": None, "root": None}

    manifest = worldfs.read_yaml(root / "world.yaml")
    g = worldfs.load_game_for(root)
    return {"g": g, "content_dir": root / "canon", "world_name": manifest["world"], "root": root}


# --- shared page shell ---------------------------------------------------------

_STYLE = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body {
  font-family: Georgia, 'Times New Roman', serif;
  color: #22201c;
  max-width: 880px;
  margin: 0 auto;
  padding: 2rem 2.5rem 4rem;
  line-height: 1.55;
  background: #fdfbf5;
}
.cover {
  text-align: center;
  padding: 3rem 1rem 2rem;
  border-bottom: 4px double #33302a;
  margin-bottom: 2rem;
}
.cover h1 { font-size: 2.4rem; margin-bottom: 0.3rem; }
.cover .subtitle { font-size: 1.15rem; color: #55504a; font-style: italic; }
h2 {
  border-bottom: 2px solid #9c8560;
  padding-bottom: 0.25rem;
  margin-top: 2.75rem;
}
h3 { color: #6b4f2a; margin-bottom: 0.25rem; }
.card {
  border: 1px solid #cdbfa0;
  border-radius: 6px;
  padding: 0.75rem 1.1rem;
  margin: 0.85rem 0;
  background: #fffdf8;
  break-inside: avoid;
}
table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
th, td { border: 1px solid #cdbfa0; padding: 0.4rem 0.65rem; text-align: left; vertical-align: top; }
th { background: #efe4cc; }
.tag {
  display: inline-block;
  background: #efe4cc;
  border-radius: 3px;
  padding: 0.05rem 0.5rem;
  font-size: 0.85em;
  margin: 0 0.25rem 0.25rem 0;
}
section { margin-bottom: 1.5rem; }
blockquote {
  border-left: 3px solid #9c8560;
  margin: 0.75rem 0;
  padding: 0.25rem 1rem;
  color: #4a463f;
  font-style: italic;
}
@media print {
  body { background: #fff; max-width: 100%; padding: 0.5in; }
  .card, table, tr, blockquote { break-inside: avoid; }
  section.page-break { break-before: page; }
  a { color: inherit; text-decoration: none; }
}
"""


def _page(title: str, subtitle: str, sections: list[str]) -> tuple[str, int]:
    body = "\n".join(sections)
    doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{esc(title)}</title>
<style>{_STYLE}</style>
</head>
<body>
<div class="cover">
  <h1>{esc(title)}</h1>
  <div class="subtitle">{esc(subtitle)}</div>
</div>
{body}
</body>
</html>
"""
    return doc, len(sections)


def _section(heading: str, inner: str) -> str:
    return f'<section class="page-break"><h2>{esc(heading)}</h2>{inner}</section>'


# --- export game ---------------------------------------------------------------

def _core_rules_html(g: dict) -> str:
    core = g["core"]
    resolution_label = str(core["resolution"]).replace("_", " ")
    crit, fumble = core["crit_on"], core["fumble_on"]
    dcs = core["dcs"]
    array = core["standard_array"]

    dc_list = ", ".join(f"{esc(name.title())} (DC {value})"
                        for name, value in sorted(dcs.items(), key=lambda kv: kv[1]))
    array_list = ", ".join(str(v) for v in array)

    return (
        f"<p>This game resolves anything uncertain with <strong>{esc(resolution_label)}</strong>: "
        f"roll the die, add the relevant modifier, and see whether the total meets or beats a "
        f"target Difficulty Class. A natural {crit} always succeeds spectacularly (a critical hit "
        f"doubles the damage dice), and a natural {fumble} always fails, no matter how good the "
        f"modifier is.</p>"
        f"<p>The GM picks a Difficulty Class to fit the moment: {dc_list}.</p>"
        f"<p>Every new character assigns this standard array of six ability scores — {array_list} — "
        f"one to each of STR, DEX, CON, INT, WIS, and CHA, however best fits the concept.</p>"
    )


def _feature_tags_html(tags: list[str]) -> str:
    return ", ".join(_title_case(t) for t in tags) if tags else "—"


def _class_html(name: str, cls: dict, max_level: int) -> str:
    rows = []
    for lvl in range(1, max_level + 1):
        row = cls.get("levels", {}).get(lvl, {})
        feats = esc(_feature_tags_html(row.get("features", [])))
        spells = esc(", ".join(_title_case(s) for s in row.get("spells", [])) or "—")
        slots = row.get("slots", {})
        slots_txt = esc(", ".join(f"L{k}: {v}" for k, v in sorted(slots.items())) or "—")
        rows.append(f"<tr><td>{lvl}</td><td>{feats}</td><td>{spells}</td><td>{slots_txt}</td></tr>")
    gear = ", ".join(_title_case(i) for i in cls.get("starting_gear", [])) or "—"
    skills = ", ".join(_title_case(s) for s in cls.get("skills", []))
    return (
        f'<div class="card"><h3>{esc(name.title())}</h3>'
        f"<p>{esc(cls.get('description', '').strip())}</p>"
        f"<p><strong>Hit die:</strong> d{cls['hit_die']} (rolled for extra hit points each level). "
        f"<strong>Starting gear:</strong> {esc(gear)}, plus {cls.get('starting_gold', 0)} gp. "
        f"<strong>Skills:</strong> choose {cls.get('skill_choices', 0)} from {esc(skills)}.</p>"
        f"<table><tr><th>Level</th><th>Features</th><th>Spells</th><th>Slots</th></tr>"
        f"{''.join(rows)}</table></div>"
    )


def _race_html(name: str, race: dict) -> str:
    bonuses = ", ".join(f"{k} +{v}" for k, v in race.get("bonuses", {}).items()) or "—"
    return (
        f'<div class="card"><h3>{esc(name.title())}</h3>'
        f"<p>{esc(race.get('description', ''))}</p>"
        f"<p><strong>Ability bonuses:</strong> {esc(bonuses)}. "
        f"<strong>Speed:</strong> {race['speed']} squares/turn.</p></div>"
    )


def _spell_html(sid: str, spell: dict) -> str:
    lvl = spell["level"]
    lvl_label = "Cantrip" if lvl == 0 else f"Level {lvl}"
    bits = []
    if "damage" in spell:
        save_txt = f", {spell['on_save']} on a successful save" if spell.get("on_save") else ""
        bits.append(f"Damage: {spell['damage']}{save_txt}")
    if "heal" in spell:
        bits.append(f"Heal: {spell['heal']}")
    if "effect" in spell:
        eff = spell["effect"]
        bits.append(f"Effect: {_title_case(eff['name'])} ({eff['duration']} rounds)")
    return (
        f'<div class="card"><h3>{esc(_title_case(sid))}</h3>'
        f'<p><span class="tag">{lvl_label}</span><span class="tag">Range {esc(str(spell["range"]))}</span>'
        f'<span class="tag">Resolve: {esc(spell["resolve"])}</span></p>'
        f"<p>{esc('; '.join(bits))}</p>"
        f"<p>{esc(spell.get('description', '').strip())}</p></div>"
    )


def _effect_html(eid: str, eff: dict) -> str:
    return (
        f'<div class="card"><h3>{esc(_title_case(eid))}</h3>'
        f"<p>{esc(eff.get('description', ''))}</p>"
        f"<p><em>{esc(eff.get('impact', ''))}</em></p></div>"
    )


def _feature_html(fid: str, feat: dict) -> str:
    return (
        f'<div class="card"><h3>{esc(_title_case(fid))}</h3>'
        f"<p>{esc(feat.get('description', ''))}</p></div>"
    )


def _item_html(iid: str, item: dict) -> str:
    bits = []
    bonus = item.get("bonus")
    if bonus:
        bits.append("Bonus: " + ", ".join(f"{k} +{v}" for k, v in bonus.items()))
    grants = item.get("grants_effect")
    if grants:
        bits.append(f"Grants effect: {_title_case(grants['name'])}")
    if item.get("cursed"):
        bits.append("Cursed")
    extra = f"<p>{esc('; '.join(bits))}</p>" if bits else ""
    return (
        f'<div class="card"><h3>{esc(_title_case(iid))}</h3>'
        f'<p><span class="tag">{item.get("price", 0)} gp</span></p>'
        f"<p>{esc(item.get('description', ''))}</p>{extra}</div>"
    )


def _monster_html(mid: str, mon: dict) -> str:
    attacks = "; ".join(
        f"{a['name']} (+{a['attack_mod']}, {a['damage']}, range {a['range']})"
        for a in mon.get("attacks", [])
    ) or "—"
    notes = f"<p><strong>Notes:</strong> {esc(mon['notes'].strip())}</p>" if mon.get("notes") else ""
    return (
        f'<div class="card"><h3>{esc(mon.get("name", mid.title()))}</h3>'
        f"<p>{esc(mon.get('description', ''))}</p>"
        f'<p><span class="tag">AC {mon["ac"]}</span><span class="tag">HP {mon["hp"]}</span>'
        f'<span class="tag">Speed {mon["speed"]}</span><span class="tag">XP {mon["xp"]}</span>'
        f'<span class="tag">Difficulty: {esc(mon.get("difficulty", "?"))}</span></p>'
        f"<p><strong>Attacks:</strong> {esc(attacks)}</p>{notes}</div>"
    )


def render_game(src: dict) -> tuple[str, int]:
    g = src["g"]
    meta = g["meta"]
    max_level = g["progression"].get("max_level", 1)

    classes_html = "".join(_class_html(n, c, max_level) for n, c in sorted(g["classes"].items()))
    races_html = "".join(_race_html(n, r) for n, r in sorted(g["races"].items()))
    spells_html = "".join(_spell_html(sid, s) for sid, s in sorted(g["spells"].items()))
    effects_html = "".join(_effect_html(eid, e) for eid, e in sorted(g["effects"].items()))

    items_by_type: dict[str, list[tuple[str, dict]]] = {}
    for iid, item in g["items"].items():
        items_by_type.setdefault(item.get("type", "other"), []).append((iid, item))
    items_html = "".join(
        f"<h3>{esc(_title_case(type_))}s</h3>" + "".join(_item_html(iid, it) for iid, it in sorted(items))
        for type_, items in sorted(items_by_type.items())
    )

    features_html = "".join(_feature_html(fid, f) for fid, f in sorted(g["features"].items()))
    bestiary_html = "".join(_monster_html(mid, m) for mid, m in sorted(game_mod.bestiary(g).items()))

    sections = [
        _section("Core Rules", _core_rules_html(g)),
        _section("Classes", classes_html),
        _section("Races", races_html),
        _section("Spells", spells_html),
        _section("Effects", effects_html),
        _section("Items", items_html),
        _section("Features", features_html),
        _section("Bestiary", bestiary_html),
    ]
    subtitle = f"Version {meta['version']} — {meta.get('description', '')}"
    return _page(f"{meta['name'].title()} Handbook", subtitle, sections)


# --- export world ----------------------------------------------------------------

def _region_table_html(content_dir: Path) -> str:
    region_path = content_dir / "maps" / "region.yaml"
    if not region_path.exists():
        return "<p>No region map authored.</p>"
    rmap = yaml.safe_load(region_path.read_text()) or {}
    nodes = rmap.get("nodes", {})
    node_rows = "".join(
        f"<tr><td>{esc(node.get('name', nid))}</td><td>{esc(node.get('terrain', ''))}</td></tr>"
        for nid, node in sorted(nodes.items())
    )
    edge_rows = []
    for edge in rmap.get("edges", []):
        a, b = edge["between"]
        edge_rows.append(
            f"<tr><td>{esc(nodes.get(a, {}).get('name', a))}</td>"
            f"<td>{esc(nodes.get(b, {}).get('name', b))}</td><td>{edge['hours']}h</td></tr>"
        )
    edge_rows = "".join(edge_rows)
    return (
        "<h3>Locations</h3>"
        f"<table><tr><th>Location</th><th>Terrain</th></tr>{node_rows}</table>"
        "<h3>Routes</h3>"
        f"<table><tr><th>From</th><th>To</th><th>Travel time</th></tr>{edge_rows}</table>"
    )


def _factions_html(content_dir: Path) -> str:
    path = content_dir / "factions.yaml"
    if not path.exists():
        return "<p>No factions authored.</p>"
    factions = yaml.safe_load(path.read_text()) or {}
    cards = []
    for fid, faction in sorted(factions.items()):
        goals = "".join(f"<li>{esc(g)}</li>" for g in faction.get("goals", []))
        relations = ", ".join(f"{k}: {v}" for k, v in faction.get("relations", {}).items()) or "none recorded"
        cards.append(
            f'<div class="card"><h3>{esc(faction.get("name", fid))}</h3>'
            f"<p><strong>Goals:</strong></p><ul>{goals}</ul>"
            f"<p><strong>Relations:</strong> {esc(relations)}</p></div>"
        )
    return "".join(cards)


def _npcs_html(content_dir: Path) -> str:
    path = content_dir / "npcs.yaml"
    if not path.exists():
        return "<p>No NPCs authored.</p>"
    npcs = yaml.safe_load(path.read_text()) or {}
    cards = []
    for nid, npc in sorted(npcs.items()):
        cards.append(
            f'<div class="card"><h3>{esc(npc.get("name", nid))}</h3>'
            f'<p><span class="tag">Location: {esc(npc.get("location", "?"))}</span>'
            f'<span class="tag">Role: {esc(npc.get("role", "?"))}</span>'
            f'<span class="tag">Disposition: {esc(npc.get("disposition", "?"))}</span></p>'
            f"<p>{esc(npc.get('description', ''))}</p>"
            f"<p>{esc(npc.get('wants', ''))}</p></div>"
        )
    return "".join(cards)


def render_world(src: dict) -> tuple[str, int]:
    g, content_dir = src["g"], src["content_dir"]
    world_name = src["world_name"] or g["meta"]["name"].title()

    setting_path = content_dir / "setting.md"
    history_path = content_dir / "history.md"
    setting_html = _md(setting_path.read_text()) if setting_path.exists() else "<p>No setting notes authored.</p>"
    history_html = _md(history_path.read_text()) if history_path.exists() else "<p>No history authored.</p>"

    sections = [
        _section("Setting", setting_html),
        _section("History", history_html),
        _section("Region Map", _region_table_html(content_dir)),
        _section("Factions", _factions_html(content_dir)),
        _section("Notable NPCs", _npcs_html(content_dir)),
    ]
    subtitle = f"World guide for {world_name}, built on {g['meta']['name'].title()} v{g['meta']['version']}"
    return _page(f"{world_name} — World Guide", subtitle, sections)


# --- export campaign ---------------------------------------------------------------

def _quest_status_table_html(root: Path) -> str:
    quests = quests_mod.list_quests(root)
    if not quests:
        return "<p>No quests offered yet.</p>"
    rows = []
    for q in quests:
        giver = q["giver"]
        giver_txt = giver["type"] if not giver.get("id") else f"{giver['type']}:{giver['id']}"
        accepted = ", ".join(q["accepted_by"]) or "—"
        deadline = "indefinite" if not q["deadline"] else f"{q['deadline']['date']} {q['deadline']['hour']:02d}:00"
        rows.append(
            f"<tr><td>{esc(q['title'])}</td><td>{esc(q['status'])}</td><td>{esc(giver_txt)}</td>"
            f"<td>{esc(accepted)}</td><td>{esc(deadline)}</td></tr>"
        )
    return (
        "<table><tr><th>Title</th><th>Status</th><th>Giver</th><th>Accepted by</th>"
        f"<th>Deadline</th></tr>{''.join(rows)}</table>"
    )


def render_campaign(src: dict) -> tuple[str, int]:
    g, content_dir, root = src["g"], src["content_dir"], src["root"]
    world_name = src["world_name"] or g["meta"]["name"].title()

    adventure_path = content_dir / "adventure.md"
    board_path = content_dir / "quest-board.md"
    adventure_html = _md(adventure_path.read_text()) if adventure_path.exists() else "<p>No adventure outline authored.</p>"
    board_html = _md(board_path.read_text()) if board_path.exists() else "<p>No quest board authored.</p>"

    sections = [
        _section("Adventure", adventure_html),
        _section("Quest Board", board_html),
    ]
    if root is not None:
        sections.append(_section("Live Quest Status", _quest_status_table_html(root)))

    subtitle = f"Campaign book for {world_name}, built on {g['meta']['name'].title()} v{g['meta']['version']}"
    return _page(f"{world_name} — Campaign Book", subtitle, sections)
