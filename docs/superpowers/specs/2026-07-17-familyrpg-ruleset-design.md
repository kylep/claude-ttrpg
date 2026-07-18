# familyrpg — ruleset design

An original, balanced, family-friendly tabletop RPG **ruleset** (a claude-ttrpg
*game* definition), built on the existing engine with **no engine changes**.
D&D-*shaped* — same mechanical spine the engine already enforces — but every
number, ability, spell, and name is our own, designed for balance and a family
table (two parents, kids). `familyrpg` is a placeholder name; trivially renamed
before we ship (it's just the directory + `meta.name`).

This spec is the **skeleton everyone authors against**. It fixes the framework
(progression curve, power cadence, parity rubric, combat math) so the actual
per-class/per-spell content — authored later, in a parallel fan-out — stays
consistent and balanced. It does *not* enumerate every ability; that's the
authoring phase.

## Design principles

- **Heroic and hopeful.** Scary-but-beatable threats; death is soft (the engine
  already gives us death saves + revival). No grimdark.
- **Kid-legible.** Each class is a one-sentence fantasy. Handbook exports read
  clean for a young player.
- **Balanced by construction.** A shared power budget per level keeps classes
  parallel; a balance-reviewer pass enforces it.
- **Engine-native.** Everything resolves through mechanics the engine already
  owns; abilities are precise text the GM executes with engine primitives.

## The engine spine we reuse (unchanged)

d20 + modifier vs DC · six attributes (STR/DEX/CON/INT/WIS/CHA), modifier =
(score − 10) // 2 · AC + HP combat · spells resolved as attack / save / auto ·
the engine's condition vocabulary (prone, grappled, hidden, poisoned,
frightened, restrained, unconscious, weakened, …) · initiative · hit dice ·
death saves · standard-array character creation · per-level spell slots. None
of this changes.

## Balance framework

**Attributes.** Standard array `[15,14,13,12,10,8]`, assigned at creation, plus
race bonuses. **Attributes are fixed for life** — classes grow through abilities,
not stat inflation. (Decision: no ASI/feat system; keeps balance clean and needs
no engine change.)

**Progression, levels 1–20.**
- Proficiency bonus: `+2` (L1–4), `+3` (L5–8), `+4` (L9–12), `+5` (L13–16),
  `+6` (L17–20).
- XP thresholds: a smooth escalating curve to 20 (exact table set in authoring;
  early levels fast, late levels long).
- HP: `hit_die` max + CON mod at L1; `hit_die` roll + CON mod each level after.

**Power cadence (the parity backbone).** Every class spends the *same* budget on
the same rhythm, so no class outshines another:
- A signature ability at **L1**, another early **identity** ability by **L3**.
- **Power spikes at L5, L11, L17** (every class gets a clearly bigger capability
  at these — a second attack, a spell tier, a defining trick).
- Meaningful new abilities at L2, 6, 9, 13, 15, 20; the "quiet" levels give a
  numeric bump (a scaling die, another use per rest) so no level feels empty.
- Authoring rubric: each class contributes comparably across **combat,
  exploration, social** by L20; the balance-reviewer scores every class against
  this cadence and flags outliers.

**Casters vs martials.**
- **Full casters (wizard, cleric, druid):** spell slots scaling to 9th-level
  spells by ~L17–19; cantrips (level 0) at will; a *known/prepared* list that
  grows per level. Curated ~8–12 spell options offered at each spell level
  (not an exhaustive list — depth without overwhelm).
- **Martials (fighter, barbarian, rogue, monk):** scaling combat
  features — extra attacks, damage riders, defensive reactions, mobility,
  resource dice (rage/ki/etc., our own versions) — budgeted to match caster
  power at each tier.

**Combat math scaling.** AC bands (unarmored ~10–12, light ~13–14, heavy ~16–18,
+2 shield); attack bonus = proficiency + attribute; damage dice scale with the
power spikes. The bestiary is tuned to this: a 4-PC party of level N handles a
"standard" encounter of tier N, with **easy / standard / tough / boss** threat
tiers as a light guideline (not a full CR system).

## Classes (7, flattened — one path each)

| Class | One-line fantasy | Role | Key attr | Type | Hit die |
|---|---|---|---|---|---|
| Fighter | The knight: armor, blades, holds the line | tank/striker | STR or DEX | martial | d10 |
| Barbarian | The berserker: rage and smash | striker/tank | STR | martial | d12 |
| Rogue | The sneak: stealth, traps, precise strikes | skirmisher | DEX | martial | d8 |
| Monk | The martial artist: fast, unarmed, evasive | skirmisher | DEX/WIS | martial | d8 |
| Wizard | The spellbook blaster | controller | INT | full caster | d6 |
| Cleric | The healer who smites the dark | support/caster | WIS | full caster | d8 |
| Druid | Turns into a bear; nature's magic | caster/shifter | WIS | full caster | d8 |

(No ranger: its defining beast-master pet is a mechanic we're deliberately not
building, and a bow-martial without it would just be a narrower fighter.)

Each class file carries: `hit_die`, `cast_attr`, `attr_priority` (for the
wizard's recommended-spread default), `skill_choices` + `skills`,
`starting_gear`, `starting_gold`, and a **`levels` table 1–20** listing the
features (and, for casters, spells learned + slots) unlocked at each level.
Signature resources (rage, ki, wild-shape) are authored
as features with precise, GM-executable mechanical text.

## Races (~15)

Classic: **human, elf, dwarf, halfling, gnome, half-orc, half-elf, dragonborn.**
Exotic / playable-monster (kid favorites): **tortle, tabaxi (cat-folk),
aarakocra (bird-folk), goliath, lizardfolk, firbolg, kenku.** Optional
little-monster PCs: **goblin, kobold.**

Each race is modest and balanced: 1–2 attribute bonuses, a speed, and one
flavorful trait (natural armor, a climb/limited-fly speed, breath weapon, etc.)
— expressed via the engine's effects/traits where enforceable, GM-flavor
otherwise. Trait power is normalized so no race is a must-pick.

## Skills (lean, ~10 proficiencies)

athletics · acrobatics · stealth · perception · investigation · arcana · nature
· medicine · survival · persuasion (with deception/intimidation folded into
social rolls, or added if the table wants them). The proficiency list is
deliberately small — the *content depth* lives in abilities and spells, not the
skill list.

## Spells (curated, original)

Levels 0 (cantrip, no slot) through 9. Each spell declares an engine-native
`resolve` (attack / save / auto), damage/effect, range, and any condition it
applies (from the engine vocabulary). Three curated lists — arcane (wizard),
divine (cleric), primal (druid) — with overlap where it fits (healing on the
divine/primal lists, utility shared). ~8–12 options per spell level per list:
enough to feel deep, few enough to choose from at a family table.

## Effects / conditions

Reuse the engine's enforced set. Add at most a couple new named conditions if a
class/spell needs one (e.g., `blessed`, `raging`) — authored as effects with
clear adv/dis impact, matching how the engine reads the effects vocabulary.

## Items

A full kit tuned to the combat math: simple + martial weapons, a few ranged,
light/medium/heavy armor + shields, adventuring gear, consumables (healing and
utility potions), and a handful of fun low-magic items (a glowing blade, boots
of leaping) for reward moments. Prices tuned to the economy so shopping matters.

## Bestiary (content, not ruleset)

A family monster set spanning the threat tiers: goblins, kobolds, giant rats &
spiders, wolves, skeletons, bandits, an ogre, an owlbear, an ooze, and a young
dragon as a capstone. Original stat blocks tuned to the scaling guideline; art
vignettes via the existing svg-art pipeline.

## Reaction rolls (free, no engine change)

A `reactions` 2d6 table in the ruleset (2: hostile → 3–5: unfriendly → 6–8:
neutral → 9–11: friendly → 12: helpful). The GM rolls `engine roll 2d6` for a
new NPC's initial disposition and reads the table; one line added to the GM
skill. No new command.

## Authoring plan (the fan-out)

Ruleset first, then content, then a campaign world (separate spec):

1. **Foundations** — core.yaml (crit/DC/array + reactions), attributes,
   progression (the 1–20 tables), economy, effects.
2. **Races** — one batch (they're small).
3. **Skills** — the lean pool.
4. **Classes** — *parallel: one agent per class*, each authoring its 1–20 level
   table + feature text against the cadence rubric.
5. **Spells** — *parallel: one agent per list* (arcane/divine/primal).
6. **Items** — one batch, tuned to the math.
7. **Features** — the feature-id → description file, assembled from the class
   outputs.
8. **Balance-review pass** — an adversarial reviewer scores every class/spell
   list against the cadence + parity rubric; flagged outliers get a fix round.
9. **`engine game validate`** — must pass clean.
10. **Bestiary** (content) — parallel batch + art.

The campaign world (setting, adventure, region map, NPCs, quests) is a **separate
design + spec** on top of this ruleset.

## Out of scope (deliberate)

Subclasses, feats/ASIs as player choices, multiclassing, and any engine change.
All can be revisited later; none are needed for a balanced, playable 1–20 family
game.
