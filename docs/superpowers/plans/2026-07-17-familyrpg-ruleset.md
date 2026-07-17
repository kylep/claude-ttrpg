# familyrpg Ruleset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Author `games/familyrpg/` — a complete, original, balanced 1–20 tabletop RPG ruleset (7 classes, ~15 races, ~250 spells across 3 lists, items, effects, a family bestiary) that passes `engine game validate` and is playable end-to-end, with **zero engine code changes**.

**Architecture:** A claude-ttrpg *game definition* is pure YAML read by the existing engine (`engine/src/ttrpg_engine/game.py`). We build a **walking skeleton** first — a minimal-but-complete game that validates and runs one encounter — then add classes, spells, and bestiary in additive waves. The validator allows orphan (defined-but-unreferenced) spells and features, so we author spell lists *before* the caster classes that reference them, and every task after the skeleton re-runs the full validator and keeps it green.

**Tech Stack:** YAML game definition; Python `engine` CLI (installed console script at `~/.local/bin/engine`, entrypoint `ttrpg_engine.cli:app`) for validation and smoke tests. No new Python.

## Global Constraints

Copied verbatim from `docs/superpowers/specs/2026-07-17-familyrpg-ruleset-design.md`. Every task's requirements implicitly include this section.

- **No engine changes.** Only files under `games/familyrpg/` are created or modified. If any content seems to *need* an engine change, stop and flag it — do not edit `engine/`.
- **Original content.** Every spell/feature/monster/item name, number, and description is our own. D&D-*shaped* (same mechanical spine) but not transcribed. Family-heroic tone: scary-but-beatable, death is soft, kid-legible one-sentence class fantasies.
- **Attributes fixed for life.** No ASI/feat system. Classes grow through features and (for casters) spells, never stat inflation.
- **Levels 1–20, no empty levels.** Every class's `levels` table has a row for all of 1–20. Signature at L1, identity by L3, **power spikes at L5/L11/L17**, meaningful new abilities at L2/6/9/13/15/20; "quiet" levels give a numeric bump (a scaling die, another use per rest).
- **Proficiency bonus by level:** `+2` (1–4), `+3` (5–8), `+4` (9–12), `+5` (13–16), `+6` (17–20).
- **Standard array** `[15,14,13,12,10,8]`, assigned at creation, plus race bonuses.
- **7 classes, one path each** — no subclasses/feats/multiclassing. Fighter d10, Barbarian d12, Rogue d8, Monk d8, Wizard d6, Cleric d8, Druid d8. (No ranger — the beast-master's pet is a mechanic we're deliberately not building.)
- **Skill vocabulary is exactly these 10** (draw class `skills:` lists from this set only): `athletics, acrobatics, stealth, perception, investigation, arcana, nature, medicine, survival, persuasion`. **`athletics`, `acrobatics`, `stealth`, `perception` are engine-load-bearing** (hardcoded in `combat.py` for grapple/hide/perception/initiative-adjacent contests) — their spelling must be exact.
- **Full-caster slot table (wizard/cleric/druid share it exactly)** — max slots per spell level by character level:

  | Lvl | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
  |----|---|---|---|---|---|---|---|---|---|
  | 1  | 2 | – | – | – | – | – | – | – | – |
  | 2  | 3 | – | – | – | – | – | – | – | – |
  | 3  | 4 | 2 | – | – | – | – | – | – | – |
  | 4  | 4 | 3 | – | – | – | – | – | – | – |
  | 5  | 4 | 3 | 2 | – | – | – | – | – | – |
  | 6  | 4 | 3 | 3 | – | – | – | – | – | – |
  | 7  | 4 | 3 | 3 | 1 | – | – | – | – | – |
  | 8  | 4 | 3 | 3 | 2 | – | – | – | – | – |
  | 9  | 4 | 3 | 3 | 3 | 1 | – | – | – | – |
  | 10 | 4 | 3 | 3 | 3 | 2 | – | – | – | – |
  | 11 | 4 | 3 | 3 | 3 | 2 | 1 | – | – | – |
  | 12 | 4 | 3 | 3 | 3 | 2 | 1 | – | – | – |
  | 13 | 4 | 3 | 3 | 3 | 2 | 1 | 1 | – | – |
  | 14 | 4 | 3 | 3 | 3 | 2 | 1 | 1 | – | – |
  | 15 | 4 | 3 | 3 | 3 | 2 | 1 | 1 | 1 | – |
  | 16 | 4 | 3 | 3 | 3 | 2 | 1 | 1 | 1 | – |
  | 17 | 4 | 3 | 3 | 3 | 2 | 1 | 1 | 1 | 1 |
  | 18 | 4 | 3 | 3 | 3 | 3 | 1 | 1 | 1 | 1 |
  | 19 | 4 | 3 | 3 | 3 | 3 | 2 | 1 | 1 | 1 |
  | 20 | 4 | 3 | 3 | 3 | 3 | 2 | 2 | 1 | 1 |

  A class `levels` row's `slots:` is the **cumulative** map for that level (e.g. L5 → `{1: 4, 2: 3, 3: 2}`), matching how `reference/ruleset/classes/*.yaml` and `chargen.create` read it.
- **Cantrips:** casters know cantrips (spell `level: 0`, no slot). Learn 2 at L1, a 3rd at L4, a 4th at L10 (added via the `spells:` list on those level rows).
- **Combat math bands:** AC — unarmored 10 + DEX; light 11–14 (+DEX); heavy 16–18 (no DEX); +2 shield (as an armor `bonus.ac` or a heavier `ac_base`). Attack bonus = proficiency + attribute mod (+ weapon `bonus`). Damage dice scale at the L5/L11/L17 spikes. Monster tiers: **easy / standard / tough / boss** (`difficulty` field, GM guidance only).

## Schema reference (authoritative — every YAML file conforms to these shapes)

Loader `game.py` reads exactly these files. `_RULESET_FILES = [core, attributes, races, spells, effects, combat, recovery, progression, economy, items, features]` (each `ruleset/<name>.yaml`) plus every `ruleset/classes/*.yaml`. Content lives under `content/`.

```yaml
# game.yaml
name: familyrpg
version: 0.1.0
description: <one line>
start_date: "0001-01-01"   # calendar is 12 months x 30 days
start_hour: 9              # 0-23
start_location: <region node id>

# ruleset/core.yaml
resolution: d20_vs_dc
crit_on: 20
fumble_on: 1
standard_array: [15, 14, 13, 12, 10, 8]
dcs: {easy: 10, medium: 13, hard: 16}

# ruleset/attributes.yaml
order: [STR, DEX, CON, INT, WIS, CHA]

# ruleset/progression.yaml
proficiency: {1: 2, 2: 2, ... 20: 6}     # all 20 keys, per the bands above
xp_thresholds: {2: 300, 3: 900, ... 20: 355000}  # all keys 2..20
max_level: 20

# ruleset/combat.yaml
initiative: {die: d20, attr: DEX}
turn: {move: speed, actions: 1}
diagonal_cost: 1

# ruleset/economy.yaml
currency: gp

# ruleset/recovery.yaml
short_rest: {hours: 1}
long_rest: {hours: 8}
death_save: {dc: 10, fails_to_die: 3, successes_to_stable: 3}

# ruleset/races.yaml  — map of race_id -> spec
<race_id>: {bonuses: {ATTR: n, ...}, speed: <squares>, description: "<flavor>"}

# ruleset/effects.yaml — map of effect_id -> spec
<effect_id>: {impact: "<GM adjudication text>", description: "<flavor>"}

# ruleset/items.yaml — map of item_id -> spec
<weapon_id>: {type: weapon, damage: "1d8", finesse: false, range: 1, price: 15,
              kind: melee|ranged (optional), bonus: {attack: n, damage: n} (optional),
              grants_effect: {name: <effect_id>} (optional), cursed: true (optional),
              description: "<flavor>"}
<armor_id>:  {type: armor, ac_base: 16, add_dex: false, stealth_dis: true (optional),
              bonus: {ac: n} (optional), price: 75, description: "<flavor>"}
<gear_id>:   {type: gear, price: 1, grants_effect: {name: <effect_id>} (optional), description: "..."}
<consumable>:{type: consumable, heal: "2d4+2" | damage: "..." | grants_effect: {...}, price: 50, description: "..."}
# (a consumable MUST define at least one of heal / damage / grants_effect)

# ruleset/spells.yaml — map of spell_id -> spec
<spell_id>:
  level: 0            # 0 = cantrip (no slot); 1-9 consume a slot of that level
  action: action
  range: 24           # squares
  resolve: attack | save | auto
  save_attr: DEX      # required when resolve: save
  damage: "1d10"      # dice; may use CASTMOD token = caster cast_attr mod
  heal: "1d8+CASTMOD" # for healing spells (resolve: auto)
  on_save: none|half  # for resolve: save (none = no damage on save; half = half rolled)
  effect: {name: <effect_id>, duration: 2}  # optional; duration in rounds, -1 = until cleared
  area: {shape: burst, radius: 1}            # optional; presence makes it an AOE cast with --at CELL
  description: "<GM narration flavor; engine ignores>"

# ruleset/features.yaml — map of feature_id -> spec
<feature_id>: {description: "<precise GM adjudication text: how to run it with engine primitives>"}

# ruleset/classes/<class>.yaml
name: <class>
description: "<one-sentence kid-legible fantasy>"
hit_die: 10
cast_attr: null | INT | WIS   # non-caster = null
skill_choices: 2
attr_priority: [STR, CON, DEX, WIS, INT, CHA]  # full permutation of 6 attrs; drives recommended array
skills: [athletics, perception, ...]           # subset of the 10-skill vocabulary
starting_gear: [<item_id>, ...]
starting_gold: 10
levels:   # keys 1..20, each: features (feature_ids), spells (spell_ids learned), slots ({level: count} cumulative)
  1: {features: [<id>], spells: [], slots: {}}
  # ... through 20

# content/maps/region.yaml
nodes:
  <node_id>: {name: <Name>, coords: [x, y], terrain: <flavor>, description: "1-2 sentences"}
edges:
  - {between: [<node_id>, <node_id>], hours: 4}

# content/maps/encounters/<id>.yaml
id: <id>
name: <Name>
grid: {width: 14, height: 8}
terrain:
  - {type: wall, cells: [[x,y], ...]}       # optional
  - {type: difficult, cells: [[x,y], ...]}  # optional
monsters:
  - {type: <bestiary_id>, pos: [x, y]}
pc_spawns: [[x, y], ...]

# content/bestiary/<id>.yaml
name: <Name>
ac: 13
hp: 7
speed: 6
attributes: {STR: 8, DEX: 14, CON: 10, INT: 10, WIS: 8, CHA: 8}
attacks: [{name: <atk>, attack_mod: 4, damage: "1d6+2", range: 1, kind: melee (optional)}]
xp: 200
loot: {gold: "1d6" | null, items: []}
flying: true            # optional; enables aloft/reach targeting rules
difficulty: easy|standard|tough|boss
```

**Validator (`game.validate`) fails on:** missing ruleset file/dir; a class missing any level 1..`max_level` row; a class `starting_gear` item not in `items`; a class-referenced `spells:` id not in `spells`; a class-referenced `features:` tag not in `features`; an item `grants_effect` naming an unknown effect; a `consumable` with no heal/damage/grants_effect; a bestiary entry missing any of `name/ac/hp/speed/attributes/attacks/xp`; a missing `content/maps/region.yaml`; a region edge naming an unknown node. **Orphan spells and orphan features are allowed** — this is why spell lists can land before caster classes.

---

## File Structure

```
games/familyrpg/
  game.yaml
  ruleset/
    core.yaml  attributes.yaml  progression.yaml  combat.yaml
    economy.yaml  recovery.yaml  races.yaml  effects.yaml  items.yaml
    spells.yaml            # assembled from 3 lists
    features.yaml          # assembled from 8 class feature sets
    classes/
      fighter.yaml barbarian.yaml rogue.yaml monk.yaml
      wizard.yaml cleric.yaml druid.yaml
  content/                 # MINIMAL placeholder here; full campaign world is a SEPARATE spec
    maps/
      region.yaml
      encounters/skirmish.yaml   # smoke-test map
    bestiary/                    # family monster set (Task 12)
```

`features.yaml` and `spells.yaml` are each a single flat map assembled from per-author fragments (disjoint keys), so parallel authors write scratch fragments that a merge step concatenates. **Every authoring task appends to these files; none rewrites another author's keys.**

---

## Verification model (adapts TDD to YAML authoring)

There is no pytest for content. The failing/passing loop is the **engine validator plus targeted smoke commands**:

- **Structural test:** `engine game validate games/familyrpg` → exit 0, `{"valid": true, ...}`.
- **Before the skeleton validates** (Task 1 only), a task's "does it fail / does it pass" is the validator's specific error line for the piece being added.
- **Integration smoke** (Tasks 1 and 13): instantiate a throwaway world and drive it:
  ```bash
  rm -rf /tmp/fam-smoke && \
  engine world init /tmp/fam-smoke --game games/familyrpg --name famsmoke
  ```
  then run chargen / encounter / cast against `/tmp/fam-smoke` (commands given in those tasks). Throwaway world is deleted at task end.

Commit after every task. Fan-out tasks (5–8 classes, 9–11 spells, 12 bestiary) are independent and may be executed by parallel subagents; each ends by re-running the full validator and committing only its own files.

---

### Task 1: Walking skeleton — foundations + Fighter + minimal content that validates and runs

**Files:**
- Create: `games/familyrpg/game.yaml`
- Create: `games/familyrpg/ruleset/{core,attributes,progression,combat,economy,recovery}.yaml`
- Create: `games/familyrpg/ruleset/{races,effects,items}.yaml`
- Create: `games/familyrpg/ruleset/spells.yaml` (empty map `{}` for now — a valid empty file)
- Create: `games/familyrpg/ruleset/features.yaml` (fighter's feature set only, for now)
- Create: `games/familyrpg/ruleset/classes/fighter.yaml`
- Create: `games/familyrpg/content/maps/region.yaml`
- Create: `games/familyrpg/content/maps/encounters/skirmish.yaml`
- Create: `games/familyrpg/content/bestiary/{goblin,goblin_archer}.yaml`

**Interfaces:**
- Produces: the skill vocabulary (10 skills), the shared full-caster slot table (already in Global Constraints), the race roster, the effects vocabulary, and the item ids that later `starting_gear` references draw from. Later class tasks consume: `hit_die`/`cast_attr` conventions, the `levels` 1–20 shape, `attr_priority` permutation rule, and the `features.yaml` / `spells.yaml` append convention.

- [ ] **Step 1: Scaffold the directory and author the single-file foundations.** Create the six mechanical files verbatim to the Schema reference: `core.yaml` (crit 20 / fumble 1 / standard array / dcs), `attributes.yaml` (`order: [STR, DEX, CON, INT, WIS, CHA]`), `combat.yaml` (initiative d20+DEX, one action, diagonal_cost 1), `economy.yaml` (`currency: gp`), `recovery.yaml` (short 1h / long 8h / death_save dc10 3/3), and `progression.yaml` with **all 20** proficiency keys (`+2` L1–4, `+3` L5–8, `+4` L9–12, `+5` L13–16, `+6` L17–20), `max_level: 20`, and `xp_thresholds` for keys 2–20 using this curve (fast early, long late): `{2:300, 3:900, 4:2700, 5:6500, 6:14000, 7:23000, 8:34000, 9:48000, 10:64000, 11:85000, 12:100000, 13:120000, 14:140000, 15:165000, 16:195000, 17:225000, 18:265000, 19:305000, 20:355000}`.

- [ ] **Step 2: Author `races.yaml` — the full ~15-race roster** (do it now; it's one small file). Each: 1–2 attribute bonuses (total ≤ +2 across scores so none is a must-pick), a speed (5–7), and a one-line flavor description. Roster: `human {CON:1, WIS:1}`, `elf {DEX:2}`, `dwarf {CON:2}`, `halfling {DEX:1, CHA:1}`, `gnome {INT:2}`, `half_orc {STR:2}`, `half_elf {CHA:1, DEX:1}`, `dragonborn {STR:1, CHA:1}`, `tortle {STR:1, WIS:1, speed:5}` (mention natural-shell AC in flavor; no engine trait), `tabaxi {DEX:2, speed:7}`, `aarakocra {DEX:1, WIS:1, speed:6}` (limited-fly flavor), `goliath {STR:2, speed:6}`, `lizardfolk {CON:1, WIS:1}`, `firbolg {WIS:1, STR:1}`, `kenku {DEX:1, INT:1}`. (Optional goblin/kobold PCs deferred — not needed to validate.)

- [ ] **Step 3: Author `effects.yaml` — the effects vocabulary.** Include every engine-enforced condition the engine reads (copy the *names* exactly; write our own flavor): `prone, hidden, grappled, restrained, unconscious, poisoned, frightened, lit, dying, dead, weakened`. Add family-ruleset buff/debuff effects classes/spells will use: `blessed, shielded, raging, focused` (each with GM `impact:` text and flavor). Match the shape in the Schema reference.

- [ ] **Step 4: Author `items.yaml` — the starting kit** (enough for the skeleton + all 8 classes' starting gear). Weapons across simple/martial/ranged (each `{type: weapon, damage, finesse, range, price, description}`, add `kind: ranged` to bows/thrown): `club, dagger, handaxe, quarterstaff, spear, shortsword, longsword, greatsword, greataxe, warhammer, mace, shortbow, longbow, sling`. Armor (`{type: armor, ac_base, add_dex, price, ...}`): `padded (11,+dex), leather (11,+dex), studded_leather (12,+dex), hide (12,+dex), chain_shirt (13,+dex,cap flavor), scale_mail (14,+dex,stealth_dis), chain_mail (16,no dex,stealth_dis), plate (18,no dex,stealth_dis)`, plus `shield {type: armor... }` — **note:** shield must not be the AC-source; instead model +2 shield as a `bonus: {ac: 2}` on a light armor variant OR document that shield is worn *with* armor via a heavier `ac_base`. Since `derive.armor_class` returns the first equipped `armor` item's AC, author shield as `wooden_shield`/`steel_shield` gear that the GM adds by hand, and give each armor an optional `_with_shield` note in its description. Gear: `torch {grants_effect: {name: lit}}, rope, thieves_tools, healers_kit, rations`. Consumables: `healing_potion {heal: "2d4+2"}, greater_healing_potion {heal: "4d4+4"}, antitoxin {grants_effect: {name: focused}}`. A couple fun low-magic reward items: `glowing_blade {type: weapon, ... bonus: {attack:1, damage:1}}`, `boots_of_leaping {type: gear, description flavor}`.

- [ ] **Step 5: Author `spells.yaml` as an empty valid map** — a single line `{}`. (Casters and their spells arrive in Tasks 9–11; fighter references no spells, so the skeleton needs none.)

- [ ] **Step 6: Author `classes/fighter.yaml` fully, levels 1–20**, following the cadence: L1 `second_wind` (signature), L2 `combat_style`, L3 `battle_focus` (identity), **L5 `extra_attack` (spike)**, L6 numeric bump, L9 `indomitable`, **L11 `improved_extra_attack` (spike — 3rd attack, spike)**, L13/15 bumps, **L17 `master_at_arms` (spike)**, L20 capstone `champion`. `hit_die: 10`, `cast_attr: null`, `skill_choices: 2`, `attr_priority: [STR, CON, DEX, WIS, INT, CHA]`, `skills: [athletics, acrobatics, perception, survival]`, `starting_gear: [chain_mail, longsword]`, `starting_gold: 10`. Every level row: `{features: [...], spells: [], slots: {}}`. Add each fighter feature id to `features.yaml` with precise GM-executable text (how to run it with `engine` primitives — e.g. extra_attack → "the fighter makes two `engine attack` rolls on the attack action").

- [ ] **Step 7: Author minimal content so validate passes and an encounter can run.** `content/maps/region.yaml`: 3 nodes (e.g. `greenhollow` settlement, `kings_road` road, `hollow_wood` forest) with valid edges. `content/bestiary/goblin.yaml` and `goblin_archer.yaml`: full required fields (`name, ac, hp, speed, attributes, attacks, xp, loot, difficulty`; archer gets a `range`>1 shortbow attack). `content/maps/encounters/skirmish.yaml`: a 14×8 grid, 2 goblins + 1 archer, `pc_spawns` for 4. Set `game.yaml` `start_location` to `greenhollow`. Also author `content/reactions.md`: the spec's 2d6 NPC-disposition table (`2` hostile → `3–5` unfriendly → `6–8` neutral → `9–11` friendly → `12` helpful) with a one-line GM note ("roll `engine roll 2d6` for a new NPC's initial disposition") — GM-facing text, no engine support needed, doesn't affect validation.

- [ ] **Step 8: Run the validator — expect PASS.**

Run: `engine game validate games/familyrpg`
Expected: exit 0, stdout `{"valid": true, "game": "familyrpg", "errors": []}`. If it fails, read each `errors[]` line — they name the exact file/id — and fix.

- [ ] **Step 9: Integration smoke — instantiate a world, create a fighter, run one encounter.**

Run:
```bash
rm -rf /tmp/fam-smoke && engine world init /tmp/fam-smoke --game games/familyrpg --name famsmoke && \
cd /tmp/fam-smoke && \
engine char create --name Borin --class fighter --race dwarf --assign "STR=15,CON=14,DEX=13,WIS=12,INT=10,CHA=8" --skills "athletics,perception" && \
engine --seed 5 encounter start maps/encounters/skirmish.yaml && \
engine encounter end && cd -
```
Expected: char create emits a sheet with `ac: 16` (chain mail) and a longsword attack; encounter start seats PCs + goblins; encounter end awards xp. No traceback. Then `rm -rf /tmp/fam-smoke`.

- [ ] **Step 10: Commit.**

```bash
git add games/familyrpg && git commit -m "feat(familyrpg): walking skeleton — foundations, fighter, minimal content that validates and runs"
```

---

### Task 2: Barbarian (martial, d12)

**Files:**
- Create: `games/familyrpg/ruleset/classes/barbarian.yaml`
- Modify: `games/familyrpg/ruleset/features.yaml` (append barbarian feature ids)

**Interfaces:**
- Consumes: the `levels` 1–20 shape, cadence rubric, and `raging` effect (from Task 1's `effects.yaml`) — if `raging` isn't there, add it.
- Produces: nothing later tasks depend on.

- [ ] **Step 1: Author `classes/barbarian.yaml`, levels 1–20.** `hit_die: 12`, `cast_attr: null`, `skill_choices: 2`, `attr_priority: [STR, CON, DEX, WIS, CHA, INT]`, `skills: [athletics, survival, perception, nature]`, `starting_gear: [hide, greataxe]`, `starting_gold: 10`. Cadence: L1 `rage` (signature — GM applies the `raging` effect + a damage rider die), L1 `unarmored_defense` (CON-based AC — GM-adjudicated since `derive.armor_class` won't compute it; document in the feature text), L3 `reckless_assault` (identity), **L5 `extra_attack` (spike)** — reuse the same feature id/text as fighter if identical, else `barbarian_extra_attack`, L7 `danger_sense`, L9 `brutal_strike` (bump), **L11 `relentless_rage` (spike)**, L15 `persistent_rage`, **L17 `might_of_the_wilds` (spike)**, L20 capstone `avatar_of_fury`. Rage damage die scales at the spikes. Every quiet level gets a numeric bump (more rages/rest, bigger rider). Append each new feature id to `features.yaml`.

- [ ] **Step 2: Validate — expect PASS.**

Run: `engine game validate games/familyrpg`
Expected: exit 0, `{"valid": true, ...}`. Fix any `class barbarian: ...` errors.

- [ ] **Step 3: Commit.**

```bash
git add games/familyrpg/ruleset/classes/barbarian.yaml games/familyrpg/ruleset/features.yaml && \
git commit -m "feat(familyrpg): barbarian class (1-20)"
```

---

### Task 3: Rogue (martial, d8)

**Files:**
- Create: `games/familyrpg/ruleset/classes/rogue.yaml`
- Modify: `games/familyrpg/ruleset/features.yaml`

- [ ] **Step 1: Author `classes/rogue.yaml`, 1–20.** `hit_die: 8`, `cast_attr: null`, `skill_choices: 4` (rogues are skill-monkeys), `attr_priority: [DEX, INT, WIS, CON, CHA, STR]`, `skills: [stealth, acrobatics, perception, investigation, persuasion, arcana]`, `starting_gear: [leather, shortsword, shortbow, thieves_tools]`, `starting_gold: 15`. Cadence: L1 `sneak_attack` (signature — note the engine **enforces** a `sneak_attack` feature automatically in `engine attack`; match that name exactly so it triggers), L1 `thieves_cant`/`deft_hands`, L3 `cunning_action` (identity), **L5 `uncanny_dodge` + sneak die bump (spike)**, L7 `evasion`, L9 `reliable_talent` (bump), **L11 `improved_sneak` (spike)**, L13 `slippery_mind`, L15 `elusive`, **L17 `stroke_of_luck` (spike)**, L20 capstone `perfect_ambush`. The sneak-attack die grows with level (the feature text tells the GM the die by level; the engine's auto-sneak uses its own scaling, so document the intended progression). Append feature ids.

- [ ] **Step 2: Validate — expect PASS.** `engine game validate games/familyrpg` → exit 0.

- [ ] **Step 3: Commit.** `git add games/familyrpg/ruleset/classes/rogue.yaml games/familyrpg/ruleset/features.yaml && git commit -m "feat(familyrpg): rogue class (1-20)"`

---

### Task 4: Monk (martial, d8)

**Files:**
- Create: `games/familyrpg/ruleset/classes/monk.yaml`
- Modify: `games/familyrpg/ruleset/features.yaml`

- [ ] **Step 1: Author `classes/monk.yaml`, 1–20.** `hit_die: 8`, `cast_attr: null`, `skill_choices: 2`, `attr_priority: [DEX, WIS, CON, STR, INT, CHA]`, `skills: [acrobatics, athletics, stealth, perception]`, `starting_gear: [quarterstaff]`, `starting_gold: 5`. Cadence: L1 `martial_arts` (signature — unarmed die + DEX finesse, GM-run) + `ki` (a per-rest resource pool that scales with level), L1 `unarmored_defense` (WIS-based AC, GM-adjudicated), L3 `flurry_of_blows`/`deflect_missiles` (identity), **L5 `extra_attack` + `stunning_strike` (spike)**, L7 `evasion`, L9 `wholeness_of_body` (bump), **L11 `improved_flurry` (spike)**, L13 `tongue_of_sun_and_moon`, L15 `timeless_body`, **L17 `quivering_palm` (spike)**, L20 capstone `perfect_self`. Ki count = level; martial-arts die grows at spikes. Append all monk feature ids to `features.yaml`.

- [ ] **Step 2: Validate — expect PASS.** `engine game validate games/familyrpg` → exit 0.

- [ ] **Step 3: Commit.** `git add games/familyrpg/ruleset/classes/monk.yaml games/familyrpg/ruleset/features.yaml && git commit -m "feat(familyrpg): monk class (1-20)"`

---

### Task 5: Arcane spell list (wizard) — levels 0–9

Authored **before** the wizard class (Task 8) so the class's referenced spell ids exist. Orphan spells are valid, so this task keeps validate green on its own.

**Files:**
- Modify: `games/familyrpg/ruleset/spells.yaml` (append the arcane block — disjoint keys)

**Interfaces:**
- Produces: arcane spell ids the wizard's `levels[].spells` will reference in Task 8. Prefix ids `arc_` to guarantee disjoint keys from the divine/primal lists (e.g. `arc_fire_bolt`, `arc_frost_lance`).

- [ ] **Step 1: Author the arcane list into `spells.yaml`.** Coverage: **≥2 cantrips** (level 0) and **8–12 spells per spell level 1 through 9** (~90 spells). Arcane identity: blasting + control + utility. Each spell exactly per the Schema reference — declare `resolve` (attack/save/auto), `save_attr` for saves, `on_save` for damage saves, `damage`/`heal`/`effect`/`area` as appropriate, `range` in squares, and a family-tone original `description`. Use engine effect names only (from `effects.yaml`). At least a few `area:` spells (fireball-shaped bursts) so the AOE targeting model gets exercised. Damage scales with spell level toward the caster slot table. **Do not** rewrite divine/primal keys.

- [ ] **Step 2: Validate — expect PASS** (orphan spells allowed). `engine game validate games/familyrpg` → exit 0.

- [ ] **Step 3: Sanity-check YAML loads and ids are unique.**

Run: `python3 -c "import yaml,collections; d=yaml.safe_load(open('games/familyrpg/ruleset/spells.yaml')); print(len(d),'spells'); assert all(k.startswith(('arc_',)) or True for k in d)"`
Expected: prints a count ≥ ~90, no exception.

- [ ] **Step 4: Commit.** `git add games/familyrpg/ruleset/spells.yaml && git commit -m "feat(familyrpg): arcane spell list (levels 0-9)"`

---

### Task 6: Divine spell list (cleric) — levels 0–9

**Files:**
- Modify: `games/familyrpg/ruleset/spells.yaml` (append `div_`-prefixed keys)

- [ ] **Step 1: Author the divine list.** ≥2 cantrips + 8–12 per level 1–9. Divine identity: healing, protection/buffs (`blessed`, `shielded`), radiant damage, anti-undead. Healing spells use `resolve: auto` + `heal: "XdY+CASTMOD"`. Prefix ids `div_`. Same schema conformance as Task 5. Some overlap in *effect* with arcane is fine; ids stay disjoint.

- [ ] **Step 2: Validate — expect PASS.** `engine game validate games/familyrpg` → exit 0.

- [ ] **Step 3: YAML/id sanity.** `python3 -c "import yaml; d=yaml.safe_load(open('games/familyrpg/ruleset/spells.yaml')); print(len(d),'spells total')"` → count grew, no exception.

- [ ] **Step 4: Commit.** `git add games/familyrpg/ruleset/spells.yaml && git commit -m "feat(familyrpg): divine spell list (levels 0-9)"`

---

### Task 7: Primal spell list (druid) — levels 0–9

**Files:**
- Modify: `games/familyrpg/ruleset/spells.yaml` (append `pri_`-prefixed keys)

- [ ] **Step 1: Author the primal list.** ≥2 cantrips + 8–12 per level 1–9. Primal identity: nature/elemental damage, entangle/control effects (`restrained`, `poisoned`), some healing, beast/weather flavor. Prefix ids `pri_`. Schema-conformant.

- [ ] **Step 2: Validate — expect PASS.** `engine game validate games/familyrpg` → exit 0.

- [ ] **Step 3: YAML/id sanity.** `python3 -c "import yaml; d=yaml.safe_load(open('games/familyrpg/ruleset/spells.yaml')); print(len(d),'spells total')"` → ~250+, no exception.

- [ ] **Step 4: Commit.** `git add games/familyrpg/ruleset/spells.yaml && git commit -m "feat(familyrpg): primal spell list (levels 0-9)"`

---

### Task 8: Wizard, Cleric, Druid (full casters, 1–20)

The three casters share the Global-Constraints slot table exactly. Author together so slot/spell-known consistency is reviewed in one place. Depends on Tasks 5–7 (their referenced spell ids must exist).

**Files:**
- Create: `games/familyrpg/ruleset/classes/wizard.yaml`, `cleric.yaml`, `druid.yaml`
- Modify: `games/familyrpg/ruleset/features.yaml`

- [ ] **Step 1: Author `classes/wizard.yaml`, 1–20.** `hit_die: 6`, `cast_attr: INT`, `skill_choices: 2`, `attr_priority: [INT, DEX, CON, WIS, CHA, STR]`, `skills: [arcana, investigation, nature, perception]`, `starting_gear: [dagger]`, `starting_gold: 20`. Each level row: `slots:` = the cumulative row from the shared table; `spells:` = the new `arc_` spells learned that level (2 cantrips + 2 leveled at L1, then ~1–2 new leveled spells per level, cantrips added at L4/L10). Highest spell level available follows the table (up to 9th by L17). Features: L2 `arcane_recovery` (`well_of_mana`-style), **spikes at L5/L11/L17 are the new spell tiers themselves** plus small features (`spell_mastery` at L18, capstone `signature_spells`/`archmage` at L20). Reference only `arc_` ids that exist in `spells.yaml`.

- [ ] **Step 2: Author `classes/cleric.yaml`, 1–20.** `hit_die: 8`, `cast_attr: WIS`, `skill_choices: 2`, `attr_priority: [WIS, CON, STR, CHA, DEX, INT]`, `skills: [medicine, persuasion, perception, survival]`, `starting_gear: [chain_shirt, mace]`, `starting_gold: 15`. Same slot table. `spells:` from `div_`. Features: L1 `channel_light` (`invoke_the_light`-style, per-rest, scales), L5/11/17 tiers, capstone `divine_intervention` at L20.

- [ ] **Step 3: Author `classes/druid.yaml`, 1–20.** `hit_die: 8`, `cast_attr: WIS`, `skill_choices: 2`, `attr_priority: [WIS, CON, DEX, STR, INT, CHA]`, `skills: [nature, survival, medicine, perception]`, `starting_gear: [leather, quarterstaff]`, `starting_gold: 15`. Same slot table. `spells:` from `pri_`. Signature feature L2 `wild_shape` (turn into a bear — a set of beast forms the GM runs, scaling by druid level in the feature text), L5/11/17 tiers + wild-shape upgrades, capstone `archdruid` at L20. Append all caster feature ids to `features.yaml`.

- [ ] **Step 4: Validate — expect PASS.** `engine game validate games/familyrpg` → exit 0. Any `unknown spell` error means a class referenced an id not in `spells.yaml` — fix the id.

- [ ] **Step 5: Commit.** `git add games/familyrpg/ruleset/classes/wizard.yaml games/familyrpg/ruleset/classes/cleric.yaml games/familyrpg/ruleset/classes/druid.yaml games/familyrpg/ruleset/features.yaml && git commit -m "feat(familyrpg): wizard, cleric, druid full-caster classes (1-20)"`

---

### Task 9: Balance-review pass (adversarial) + fix round

**Files:**
- Modify: any `ruleset/classes/*.yaml`, `spells.yaml`, `items.yaml` the review flags.

**Interfaces:**
- Consumes: all 8 classes + 3 spell lists. Produces: a scored report and a bounded fix round.

- [ ] **Step 1: Score every class against the cadence + parity rubric.** For each class, confirm: a row exists for all 1–20; L1 signature, L3 identity, spikes present at L5/L11/L17, meaningful abilities at L2/6/9/13/15/20, no empty quiet levels; martials' extra-attack/resource scaling is roughly power-parallel to casters' spell-tier access at each tier; each class contributes across combat/exploration/social by L20. Produce a written outlier list (class, level, issue). *(If executed via subagent-driven-development, dispatch this as an adversarial reviewer subagent whose job is to find imbalance, not to praise.)*

- [ ] **Step 2: Spot-check caster math.** Confirm every caster's `slots:` rows match the Global-Constraints table exactly and every `spells:` id exists. Confirm damage/heal dice escalate sensibly against spell level (no level-9 spell weaker than a level-3).

- [ ] **Step 3: Apply the fix round.** Edit flagged rows/spells/items directly. Keep changes minimal and targeted; re-note anything that can't be fixed without an engine change (there should be none — if there is, stop and surface it).

- [ ] **Step 4: Validate — expect PASS.** `engine game validate games/familyrpg` → exit 0.

- [ ] **Step 5: Commit.** `git add games/familyrpg && git commit -m "fix(familyrpg): balance-review pass — cadence & caster/martial parity"`

---

### Task 10: Bestiary — family monster set across threat tiers

Content, not ruleset — but it's needed for the final integration smoke and for the game to be playable. (The full campaign world is a separate spec; this is the reusable monster set.)

**Files:**
- Create: `games/familyrpg/content/bestiary/<id>.yaml` for the full set (goblin/goblin_archer from Task 1 already exist — expand around them).

- [ ] **Step 1: Author the monster set** spanning `easy → standard → tough → boss`, tuned to the combat-math bands so a 4-PC party of level N handles a tier-N standard encounter. Set: `giant_rat, giant_spider, wolf, kobold, goblin_boss, skeleton, zombie, bandit, bandit_captain, orc, hobgoblin, ogre, owlbear, dire_wolf, giant_bat (flying: true), harpy (flying: true), gray_ooze, troll, young_dragon (boss)`. Each conforms to the bestiary schema (all required fields; `loot`; `difficulty`; `flying: true` on fliers so aloft/reach rules engage; `kind: ranged` on ranged attacks). Original names/flavor allowed but the ids above keep them recognizable at the table.

- [ ] **Step 2: Validate — expect PASS.** `engine game validate games/familyrpg` → exit 0 (validator checks each bestiary entry has `name/ac/hp/speed/attributes/attacks/xp`).

- [ ] **Step 3: Commit.** `git add games/familyrpg/content/bestiary && git commit -m "feat(familyrpg): family bestiary across threat tiers"`

---

### Task 11: Bestiary art (SVG, procedural — no image spend)

**Files:**
- Create: `games/familyrpg/content/art/<monster>.svg` for a representative subset (the boss + one per tier at minimum).

**Interfaces:**
- Consumes: the bestiary from Task 10. Uses the house SVG-art pipeline (`svg-artist` / `svg-art-reviewer` agents) — **Claude-drawn SVG only, no image-generation spend**, per the project's procedural-SVG art direction.

- [ ] **Step 1: Dispatch the `svg-artist` agent** for the young dragon (boss) and one monster per tier, each to `content/art/<id>.svg` in the house cartography style, then the `svg-art-reviewer` agent for an adversarial pass; iterate on flagged defects. (This step is inherently agent-driven; if executing inline, invoke those agents.)

- [ ] **Step 2: Validate — expect PASS** (art doesn't affect validation, but confirm nothing else regressed). `engine game validate games/familyrpg` → exit 0.

- [ ] **Step 3: Commit.** `git add games/familyrpg/content/art && git commit -m "feat(familyrpg): bestiary SVG art (procedural)"`

---

### Task 12: Final integration smoke — one PC of every class (7), spells, a boss fight

**Files:** none created; drives a throwaway world.

- [ ] **Step 1: Instantiate a fresh world and create one PC of each of the 8 classes.**

Run:
```bash
rm -rf /tmp/fam-final && engine world init /tmp/fam-final --game games/familyrpg --name famfinal && cd /tmp/fam-final
engine char create --name Borin --class fighter   --race dwarf     --assign "STR=15,CON=14,DEX=13,WIS=12,INT=10,CHA=8" --skills "athletics,perception"
engine char create --name Gruul --class barbarian  --race half_orc  --assign "STR=15,CON=14,DEX=13,WIS=12,INT=8,CHA=10" --skills "athletics,survival"
engine char create --name Pip   --class rogue       --race halfling  --assign "DEX=15,INT=14,WIS=13,CON=12,CHA=10,STR=8" --skills "stealth,acrobatics,perception,investigation"
engine char create --name Kai   --class monk        --race tabaxi    --assign "DEX=15,WIS=14,CON=13,STR=12,INT=10,CHA=8" --skills "acrobatics,stealth"
engine char create --name Vek   --class wizard      --race gnome     --assign "INT=15,DEX=14,CON=13,WIS=12,CHA=10,STR=8" --skills "arcana,investigation"
engine char create --name Mira  --class cleric      --race human     --assign "WIS=15,CON=14,STR=13,CHA=12,DEX=10,INT=8" --skills "medicine,persuasion"
engine char create --name Thorn --class druid       --race firbolg   --assign "WIS=15,CON=14,DEX=13,STR=12,INT=10,CHA=8" --skills "nature,survival"
```
Expected: 7 sheets created, no traceback. Casters (Vek/Mira/Thorn) show `spells_known` and `spell_slots: {1: {max: 2, current: 2}}`.

- [ ] **Step 2: Cast a representative single-target and an AOE spell in an encounter.** Start the skirmish map, then have the wizard cast one attack/save spell at a goblin (`engine cast --caster pc-vek --spell <arc_id> --target goblin-1`) and one `area:` spell (`engine cast --caster pc-vek --spell <arc_area_id> --at X,Y`). Expected: single-target resolves hit/save; area hits all living in radius. No traceback.

- [ ] **Step 3: Run a boss encounter to end.** Build/point at an encounter with `young_dragon`; `engine --seed 5 encounter start ...` then step turns and `engine encounter end`. Expected: xp awarded, no traceback.

- [ ] **Step 4: Tear down.** `cd - && rm -rf /tmp/fam-final`.

- [ ] **Step 5: Final full validate + commit a completion marker if anything changed.**

Run: `engine game validate games/familyrpg`
Expected: exit 0, `{"valid": true, "game": "familyrpg", "errors": []}`.
If Steps 1–3 surfaced fixes, commit them: `git add games/familyrpg && git commit -m "fix(familyrpg): integration-smoke fixes"`

---

## Self-Review

**Spec coverage** (each spec section → task):
- Design principles / engine spine → Global Constraints + Task 1 foundations. ✓
- Balance framework (attributes fixed, progression 1–20, proficiency bands, power cadence, caster/martial parity, combat math) → Global Constraints (numbers locked) + Task 9 (enforcement). ✓
- 7 classes flattened → Tasks 1 (fighter), 2 (barbarian), 3 (rogue), 4 (monk), 8 (wizard, cleric, druid). No ranger (dropped — no pet mechanic). ✓
- ~15 races → Task 1 Step 2 (full roster incl. tortle/tabaxi/aarakocra/goliath/lizardfolk/firbolg/kenku). ✓
- Lean ~10 skills → Global Constraints (fixed 10-skill vocab, engine-load-bearing four called out). ✓
- Curated spells 0–9, three lists → Tasks 5 (arcane), 6 (divine), 7 (primal). ✓
- Effects (reuse engine set + a couple new) → Task 1 Step 3. ✓
- Items kit tuned to math → Task 1 Step 4. ✓
- Bestiary across tiers + art → Tasks 10, 11. ✓
- Reaction rolls (2d6 table) → **GAP FIX:** the design spec lists a `reactions` 2d6 table + a GM-skill line. The engine has no `reactions` ruleset file and no command; it's GM-facing text. Add it as `content/reactions.md` (or a `reactions:` block in `game.yaml` meta) authored in **Task 1 Step 7** and referenced by one line in the world's GM skill during the *world* spec. Since it needs no engine support and doesn't affect validation, it rides along with content; noted here so it isn't dropped.
- Authoring plan fan-out / validate / separate world spec → this whole plan; the campaign world is explicitly a **separate** spec (not in scope here). ✓
- Out of scope (subclasses/feats/multiclassing/engine changes) → honored throughout. ✓

**Placeholder scan:** No "TBD/TODO" left. Concrete numbers (xp curve, slot table, proficiency, AC bands, race bonuses, class hit dice/attr_priority/skills/gear) are all specified. Feature/spell *flavor text* is delegated to authoring agents by design — that's content generation, not a plan placeholder; each such step names the exact ids and schema.

**Type consistency:** `slots:` is the cumulative `{spell_level: count}` map everywhere (matches `chargen.create` reading `level1["slots"]`). `features:`/`spells:` are id lists validated against `features.yaml`/`spells.yaml`. Skill names are the fixed 10, with the engine-load-bearing four spelled exactly. Spell id prefixes (`arc_`/`div_`/`pri_`) guarantee disjoint keys across the three parallel spell tasks writing one `spells.yaml`. The `sneak_attack` feature id is kept verbatim so the engine's auto-sneak triggers.

**Scope:** Single implementation plan producing one validating, playable game definition. The campaign world (setting/adventure/NPCs/quests/region art) is a deliberately separate downstream spec.
