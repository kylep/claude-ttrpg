# Thornbury and the Barrowdeep — GM Outline

A one-shot or short arc: hire in Thornbury, travel the Old Road, fight
an ambush, camp in Barrow Woods, clear two chambers of the reopened
barrow, and put down the Barrow King. This file is GM reference —
nothing here is loaded by the engine.

DCs below cite `ruleset/core.yaml` `dcs: {easy: 10, medium: 13, hard: 16}`.

## Beat 1 — Hire (Thornbury)

The party meets **Reeve Halda** (`content/npcs.yaml`), who has been
fielding complaints about goblin raids out of Barrowdeep for two
weeks. She offers 100 gp on the party's return with proof the barrow
is cleared (a token from the inner chambers is proof enough).
**Innkeeper Bram** will trade rumors for a bought round: the ambush
site on the Old Road, the flood-opened passage, and talk of something
"crowned" moving in the dark. A DC 10 (easy) social check or simply
buying Bram a drink gets the full rumor list; digging for the
Moot's salvage-rights dispute (see `history.md` hook three) is a DC 13
(medium) check, since Bram is nervous about repeating it.

## Beat 2 — Travel to the Old Road (4h)

`thornbury` → `old-road`, 4 hours. **Pedlar Okko** is camped at the
old-road node and trades at list price (`ruleset/items.yaml`). A DC 13
(medium) Perception check while on the road spots goblin sign before
the ambush triggers, granting the party a surprise round if the GM
wants to reward it.

## Beat 3 — Ambush (`maps/encounters/road-ambush.yaml`)

2 goblins and 1 goblin archer spring from the scrub lining the road.
The archer holds range in the open ground; the goblins close through
the difficult scrub. This is the easiest fight of the adventure — a
warning shot, not the main event.

## Beat 4 — Camp at Barrow Woods (3h travel + rest)

`old-road` → `barrow-woods`, 3 hours. Barrow Woods is a safe forest
camp — recommend a short or long rest here (`ruleset/recovery.yaml`)
before pushing into the barrow. A DC 10 (easy) Survival check keeps
the camp unnoticed; failure means a goblin scout finds the party and
the GM may run a second, smaller skirmish at their discretion.

## Beat 5 — Into the Barrow (1h travel)

`barrow-woods` → `barrowdeep`, 1 hour. This is the dungeon proper, run
as two encounters:

### Encounter A — `maps/encounters/barrow-hall.yaml`

2 barrow hounds guard the pillared outer hall. They flank through the
gaps between pillars and are drawn to noise — a loud fight here can be
heard from the tomb beyond (see Encounter B).

### Encounter B — `maps/encounters/kings-tomb.yaml`

The boss fight: **the Barrow King** with one goblin honor-guard, in
his rubble-choked burial chamber. His dread wail (see
`content/bestiary/barrow_king.yaml`) frightens whoever it hits; the GM
should apply the `frightened` effect by hand
(`effect add --target <pc> --name frightened --duration 2`) rather
than expecting the engine to do it automatically. A DC 16 (hard)
Athletics or Perception check finds safe footing across the rubble
(`terrain: difficult`) and avoids the extra movement cost for one
turn.

## Beat 6 — Return and Reward

`barrowdeep` → `barrow-woods` → `old-road` → `thornbury` (retrace the
route, 1h + 3h + 4h). On presenting proof the barrow is cleared,
Reeve Halda pays **100 gp** to the party and the GM should run:

```
xp grant --amount 100 --reason "cleared the Barrowdeep for Reeve Halda"
```

as a flat bonus on top of encounter XP (encounter XP already splits
per `combat.end`; the quest bonus does not).

## Loot / Reward Table

| Source                          | Gold             | Items                | XP  |
|----------------------------------|------------------|-----------------------|-----|
| Goblin (x2, road-ambush)         | 1d6 each          | —                      | 50 each |
| Goblin archer (road-ambush)      | 1d4               | —                      | 50  |
| Barrow hound (x2, barrow-hall)   | —                 | —                      | 100 each |
| Goblin honor guard (kings-tomb)  | 1d6               | —                      | 50  |
| The Barrow King (kings-tomb)     | 4d10              | `kings_circlet` (200 gp value) | 450 |
| Quest reward (Reeve Halda)       | 100 flat          | —                      | 100 (flat grant) |

Total encounter XP for a full clear: 850 (150 / 200 / 500 across the
three fights), plus the 100 xp quest bonus — enough to push most
parties to level 2 (`xp_thresholds: {2: 300}` in
`ruleset/progression.yaml`) with room to spare toward level 3 (900).
