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

---

# Act 2 — Below the Barrowdeep

The flood that opened the barrow did not stop at the tomb. Behind the
Barrow King's dais a stair descends into Hravik's drowned undercroft:
the Sunken Stair down to the water line, and the Drowned Gallery
beyond it, where his oath-priestess Sigrun was drowned at his
interment and has been waiting ever since. This act is tuned for a
party of level 3-5; run it after the King falls, or as a return trip
when the tremors start. DCs again cite `ruleset/core.yaml`
`dcs: {easy: 10, medium: 13, hard: 16}`.

## Beat 7 — The Water Rises (Barrowdeep)

With the King down, the tremors from `history.md` hook one make
themselves felt: the eastern slope slumps again and black water climbs
the tomb steps. **Wenna the Diver** (`content/npcs.yaml`) is camped at
the barrow mouth — a river-salvager hired by the Moot faction from
hook three, now too frightened to finish the job. For 20 gp or a
salvage share she hands over her depth map and her warning about the
"grey woman in the water." Reeve Halda, if consulted, doubles the
original purse (another **100 gp**) to have the undercroft sealed for
good; she will not say out loud that the Moot's broker had a diver
down there first. A DC 13 (medium) social check gets Wenna to admit
who paid her.

## Beat 8 — The Sunken Stair (1h travel)

`barrowdeep` → `sunken-stair`, 1 hour of rope-work down flooded
switchbacks. Run `maps/encounters/sunken-stair.yaml`: two mire
creepers drop from the balustrades while a sunken warden — one of
Hravik's drowned honor guard — wades up the steps with its hooked
pike. The wet treads (`terrain: difficult`) punish careless
footing; a DC 13 (medium) Acrobatics or Athletics check on entry
lets a PC ignore the extra movement cost for one turn. The creepers'
venom and the warden's leg-hook are applied by hand — the exact GM
commands are in each bestiary file's `notes:`.

## Beat 9 — The Drowned Gallery (2h travel)

`sunken-stair` → `drowned-gallery`, 2 hours along a half-submerged
processional hall. Recommend a short rest at the stair foot first —
there is no safe camp beyond it. The gallery fight
(`maps/encounters/drowned-gallery.yaml`) is the act's boss: **the
Pale Oathwife** (difficulty: hard) attended by a sunken warden and a
mire creeper, in knee-deep floodwater (`terrain: difficult`). Her
drowning benediction poisons at range (see
`content/bestiary/pale_oathwife.yaml` `notes:`), and if anyone is
carrying the `kings_circlet` she singles them out — a DC 16 (hard)
Insight or Religion check before the fight reveals that surrendering
the circlet to the water will end the haunting without bloodshed, at
the cost of the 200 gp treasure. Parties that parley (DC 16 hard,
she has heard every oath a living tongue can make) may broker the
same trade.

## Beat 10 — Sealing the Deep

However the Oathwife ends — destroyed, or paid in gold-and-pearl —
the water stops rising within the hour. Collapsing the stair behind
them is a DC 13 (medium) Athletics check with rope and pry-bars (no
roll needed if the party thinks to use the warden's pike as a lever).
Back in Thornbury, Halda pays the second **100 gp** purse and the GM
runs:

```
xp grant --amount 200 --reason "sealed the undercroft below the Barrowdeep"
```

as a flat bonus on top of encounter XP. If the party gave up the
circlet, Halda quietly kills the Moot's salvage-rights scheme; if
they kept it, the broker comes asking — a hook for whatever comes
next.

## Act 2 Loot / Reward Table

| Source                                | Gold      | Items | XP  |
|----------------------------------------|-----------|--------|-----|
| Mire creeper (x2, sunken-stair)        | —         | —      | 250 each |
| Sunken warden (sunken-stair)           | 2d6       | —      | 350 |
| Mire creeper (drowned-gallery)         | —         | —      | 250 |
| Sunken warden (drowned-gallery)        | 2d6       | —      | 350 |
| The Pale Oathwife (drowned-gallery)    | 6d10      | —      | 700 |
| Quest reward (Reeve Halda, Act 2)      | 100 flat  | —      | 200 (flat grant) |

Total Act 2 encounter XP for a full clear: 2150 (850 at the stair,
1300 in the gallery), plus the 200 xp quest bonus. A party that
finished Act 1 around 950 xp ends Act 2 near 3300 — past level 4
(`xp_thresholds: {4: 2700}`) and halfway to level 5 (6500), with the
new level-2 spell slots coming online exactly when the Oathwife
starts poisoning people.
