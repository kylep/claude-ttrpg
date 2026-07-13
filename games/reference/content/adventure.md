# Thornbury and the Barrowdeep — GM Outline

A one-shot or short arc: hire in Thornbury, travel the Old Road, fight
an ambush, camp in Barrow Woods, clear two chambers of the reopened
barrow, and put down the Barrow King. This file is GM reference —
nothing here is loaded by the engine.

DCs below cite `ruleset/core.yaml` `dcs: {easy: 10, medium: 13, hard: 16}`.

## Side Quests — The Thornbury Board

Thornbury keeps a standing quest board outside the moot-hall
(`content/quest-board.md`), independent of Reeve Halda's barrow contract
below. Introduce it in the same session 1 Thornbury scene as Beat 1,
once the party has spoken to Halda and Bram — two notices are already
pinned up, and the GM should run both setup commands from
`quest-board.md` before the party leaves for the Old Road, so `engine
quest list` shows both as `offered` from session 1 onward:

```
engine quest offer --title "Find Tuffles" --desc "..." --giver npc:farmer_tobin --gold 15 --items healing_potion --deadline 1204-04-17
engine quest offer --title "The Graveyard Risings" --desc "..." --giver world --items graveward_coin --xp 50 --spawn
```

Neither quest gates travel to the Old Road — the party can accept
either, both, or neither before pushing on to Act 1, and can return to
either at any point ("Find Tuffles" has a year-long deadline; "The
Graveyard Risings" has none). See `content/quest-board.md` for the full
in-world notices, resolution spreads, and the two new bestiary entries
(`content/bestiary/grave_walker.yaml`, `content/bestiary/hollow_sexton.yaml`)
needed to run the graveyard encounter (`maps/encounters/graveyard.yaml`)
and, if talk fails, the showdown with whatever is causing it
(`maps/encounters/graveyard-vigil.yaml`). The graveyard is not a
region-map node — it's Thornbury's own yard, run as a same-location
encounter (no `engine travel` needed) directly off the `thornbury` node
in `maps/region.yaml`, the same way a home-village skirmish would be.

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

| Source                          | Gold             | Items                | XP (party pool) |
|----------------------------------|------------------|-----------------------|-----|
| Goblin (x2, road-ambush)         | 1d6 each          | —                      | 200 each |
| Goblin archer (road-ambush)      | 1d4               | —                      | 200  |
| Barrow hound (x2, barrow-hall)   | —                 | —                      | 400 each |
| Goblin honor guard (kings-tomb)  | 1d6               | —                      | 200  |
| The Barrow King (kings-tomb)     | 4d10              | `kings_circlet` (200 gp value) | 1800 |
| Quest reward (Reeve Halda)       | 100 flat          | —                      | 100 (flat grant, full amount to each PC) |

Bestiary `xp:` values are a party pool sized for 4 PCs — `engine
encounter end` splits each encounter's pool with `total // len(members)`,
while `engine xp grant` credits its flat amount in full to every PC (it
does not split). Worked per-PC math for a 4-PC party, from the actual
rosters in `maps/encounters/*.yaml` and the bestiary above:

- road-ambush: (200 + 200 + 200) // 4 = 600 // 4 = **150 xp/PC**
- barrow-hall: (400 + 400) // 4 = 800 // 4 = **200 xp/PC**
- kings-tomb: (1800 + 200) // 4 = 2000 // 4 = **500 xp/PC**
- quest grant (Reeve Halda): **100 xp/PC**, in full, not split

Per-PC total after Act 1: 150 + 200 + 500 + 100 = **950 xp** — past
the level-3 threshold (`xp_thresholds: {3: 900}` in
`ruleset/progression.yaml`) with a small cushion, and well short of
level 4 (2700).

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

| Source                                | Gold      | Items | XP (party pool) |
|----------------------------------------|-----------|--------|-----|
| Mire creeper (x2, sunken-stair)        | —         | —      | 1000 each |
| Sunken warden (sunken-stair)           | 2d6       | —      | 1400 |
| Mire creeper (drowned-gallery)         | —         | —      | 1000 |
| Sunken warden (drowned-gallery)        | 2d6       | —      | 1400 |
| The Pale Oathwife (drowned-gallery)    | 6d10      | `oathwifes_torc` (300 gp value) | 2800 |
| Quest reward (Reeve Halda, Act 2)      | 100 flat  | —      | 200 (flat grant, full amount to each PC) |

Same per-PC math as Act 1, continuing from the 950 xp/PC each
character has banked by the end of it:

- sunken-stair: (1000 + 1000 + 1400) // 4 = 3400 // 4 = **850 xp/PC**
- drowned-gallery: (1000 + 1400 + 2800) // 4 = 5200 // 4 = **1300 xp/PC**
- quest grant (Reeve Halda, Act 2): **200 xp/PC**, in full, not split

Per-PC Act 2 gain: 850 + 1300 + 200 = 2350 xp. Cumulative per-PC
total: 950 + 2350 = **3300 xp** — comfortably clear of the level-4
threshold (`xp_thresholds: {4: 2700}`), about 600 xp past it, with
the new level-2 spell slots coming online exactly when the Oathwife
starts poisoning people. Level 5 (6500) is headroom reserved for
future content beyond this two-act adventure — it is not reachable
from the encounters and quest grants shipped here.

---

# Act 3 — The Four Grave-Wards

The Pale Oathwife does not simply die when she falls: something that
has been listening for three centuries lets go. The instant she goes
still, a low tremor rolls through the flooded stone and four sealed
doors the party never noticed — set flush into the undercroft wall
past the gallery, unmarked by damp or moss the way nothing else down
here is unmarked — wake at once, each one sighing open by a hand's
width and no further. These are Hravik's grave-wards: reliquary vaults
his household built to hold what a king's household does not trust to
a single tomb, warded the old way, on oath and blood rather than lock
and key. Sigrun kept the wards live from the water for three hundred
years without ever needing to explain them to anyone; with her gone,
they have woken up needing an explanation, and they choose to test
one.

Each ward "abides a single heartbeat." Approach one door as a group
and it seals itself shut, cold and final, before anyone's hand
touches it; approach alone and it opens the rest of the way, revealing
a short passage to a trial chamber keyed to a calling the ward
recognizes — fighter, rogue, cleric, wizard — one door per nature, none
interchangeable, none forceable. A party of any other composition
either has doors that never open, or a trial no one currently in the
party can attempt; a classic four-class party finds one door for each
of them and no leftovers. This is the game's structural excuse for a
split party, and the mandate is explicit rather than incidental: all
four trials are meant to run as (near-)concurrent solo scenes, not a
single-file dungeon crawl four times over.

## Beat 11 — The Ward-Hall (`drowned-gallery` → `ward-hall`, 1h)

The party travels together — this leg is not split, only the trial
doors are. `engine travel --to ward-hall` (no `--pcs`, the whole party
moves as one and the world clock ticks once) brings everyone into a
short domed chamber standing above the last of the floodwater, dry
enough that torches hold. Four low iron doors are set into the four
walls, each cold to the touch and each etched with a device any PC can
recognize as their own calling once they are close enough to feel it
sigh open for them alone: a crossed blade and shield; a latch and key;
a censer and scale; a bound circle and eye. In the chamber's center, a
shallow basin holds water that never quite goes still — the **Font of
Unbinding**, more on which below. A DC 13 (medium) Religion or Arcana
check on the door-devices confirms what Beat 12-15 assume: these are
tests, not traps, and killing what waits inside is expected to end
each one cleanly.

## Beats 12-15 — The Four Trials

Each trial is a **solo encounter**: run `engine encounter start
maps/encounters/ward-<class>.yaml --pcs <that PC's id>` for exactly one
PC. The engine seats only that PC (solo maps ship one `pc_spawns`
entry), participants are recorded on the encounter, and `engine
encounter end` credits that encounter's full monster xp to the lone
participant — nobody else gets a cut, because nobody else was there.
There is no separate quest-completion xp grant this act (contrast Acts
1-2's `xp grant` bonuses): **the relic each ward yields is the reward**,
in place of a flat bonus, on top of whatever xp the fight itself pays
out. See the survivability notes in each bestiary file
(`content/bestiary/ward_captain.yaml`, `latchwight.yaml`,
`unshriven_judge.yaml`, `bound_sentinel.yaml`) for the hit-chance and
expected-damage math behind each design; the summary is in the reward
table below.

### Beat 12 — The Duelist's Ward (fighter)

The door opens on a bare, clean floor between two broken doorposts —
`maps/encounters/ward-fighter.yaml` — and **the Ward-Captain's Echo**
salutes before it attacks, exactly as it has saluted every soul foolish
enough to answer this door for three hundred years. It fights fair,
which is the whole trial: no terrain gimmick, no add, just one duel a
level 4-5 fighter is expected to win on the merits. On its defeat, the
Echo's blade is the ward's yield — see `doubtwhisper` below. A DC 13
(medium) Insight check made *during* the duel (not before — the ward
doesn't reveal this until blades are already crossed) notices the Echo
pulls exactly one strike in three, as if some part of it still doesn't
want the fight it's bound to have.

### Beat 13 — The Latch-Vault (rogue)

Beyond this door is shelving, half-collapsed, over a floor of rubble
and trip-latches — `maps/encounters/ward-rogue.yaml` — guarded by **the
Latchwight**, a key-shaped ward-spirit that skitters the difficult
cells (`terrain: difficult`) without penalty while everyone else pays
the extra movement cost to cross them. A DC 13 (medium) Acrobatics
check on entry lets the rogue ignore the difficult-terrain cost for one
turn, same convention as Act 2's flooded treads; a DC 10 (easy)
Perception check before engaging spots which shelving is still going
to fall if leaned on, which the GM can use to open an environmental
option (shove the Latchwight under it) instead of a straight fight.
On defeat it yields the vault's own boots — see `hushstep_boots` below.

### Beat 14 — The Judgment Ward (cleric)

The censer-and-scale door opens on a small dais chamber ankle-deep in
grave-ash — `maps/encounters/ward-cleric.yaml` — where **the Unshriven
Judge** names the cleric's failings aloud in a dead language before
it swings its gavel-rod. A DC 16 (hard) Religion or Insight check,
made before combat, lets the cleric correctly answer the Judge's first
charge; the GM may reward this with `--adv` on the cleric's first
attack roll rather than skipping the fight outright — the ward wants
to see the calling proven in combat, not merely argued with. On defeat
it yields its talisman of office — see `oathlight_talisman` below.

### Beat 15 — The Bound Ward (wizard)

The bound-circle door opens on a rune-scorched chamber — `maps/encounters/ward-wizard.yaml` —
holding **the Bound Sentinel**, a mindless construct raised to let
nothing living leave its circle unproven. A DC 13 (medium) Arcana check
on the rune-lattice tells a wizard something worth knowing before they
commit spell slots: the warding answers to intent and edge, not to raw
force — `magic_missile`'s auto-hit resolve ignores the lattice (and the
Sentinel's AC) entirely, while `fire_bolt` has to beat it fair. This is
mechanically true, not just flavor: see the bestiary notes on
`bound_sentinel.yaml` for the math. On defeat it yields the lens from
its own rune-circle — see `wardglass_lens` below.

## The Font of Unbinding

Whatever answers the wards also keeps the shallow basin in the
ward-hall's center from ever going still. The Font is not a shrine to
any god the party's cleric would recognize by name — it is closer to a
held breath, three centuries of one woman's patience with nowhere left
to go once she let go of it. It has one function left in it:
**lifting a curse laid by anything the ward-hall produced.** This is
the ritual site for dispelling `doubtwhisper` (see below) — the
mechanic is `engine item dispel --actor <pc> --item doubtwhisper`,
GM-gated, not automatic. To earn the GM's go-ahead to run it, the
cursed PC must return to the ward-hall, lay the blade in the Font's
water, and speak the confession the blade has been whispering back at
them — in practice, a DC 13 (medium) Religion, Insight, or Persuasion
check, played as a genuine beat of table roleplay rather than a dice
formality. Success: the whispering stops (`engine item dispel`
lifts `oath_whisper` but leaves the blade's `bonus: {attack: 1, damage:
2}` intact — a cursed weapon dispelled is still a fine weapon).
Failure doesn't lock the ritual out forever; it just means the
confession wasn't honest enough yet, and the Font will still be there
next session.

## Curse Reveal — When Does the Fighter Learn?

Not immediately, and that's deliberate. `doubtwhisper` doesn't
announce itself on the swing that kills the Ward-Captain's Echo, or
even on the walk back to camp — the whisper is quiet, and a fighter
riding a battle high has better things to listen to. The mechanical
and narrative reveal are the same moment: **the first time the fighter
tries to lay the blade down** — to clean it, trade it to a companion,
switch back to their old longsword, anything — `engine unequip --actor
<pc> --item doubtwhisper` returns the `cursed` error, and that refusal
*is* the reveal. Narrate the whisper sharpening into words at exactly
that moment: the blade does not want to be set down, and says so. Any
GM who wants an earlier tell can allow a DC 16 (hard) Insight check the
first evening the fighter carries it, unprompted, as a "something's
not right" hook — but the hard reveal, the one the player can't
rules-lawyer around, is the failed unequip.

## GM Sidebar — Running a Split Party

Four solo trials in one sitting is an interleaving problem, not a
sequencing problem — don't run all of one PC's trial start-to-finish
while three players wait.

- **Travel together, split for the trial.** Beat 11 moves the whole
  party with a single `engine travel --to ward-hall` (one clock tick).
  The split happens only at the doors: run `engine encounter start
  maps/encounters/ward-<class>.yaml --pcs <pc-id>` one at a time. If
  your table wants an even earlier, harder split — a PC arriving at
  the ward-hall ahead of the others — send them alone with `engine
  travel --to ward-hall --pcs <pc-id>` instead; that PC's hour ticks
  the shared world clock immediately, and the rest of the party ticks
  it again, separately, whenever they follow. There is only one world
  clock in v1 — it is not per-PC — so a staggered arrival costs the
  table two clock advances instead of one. Beat 11's simultaneous
  version is the cheaper, easier default; use the staggered version
  only when the story wants the gap.
- **Interleave the scenes, not the encounters.** Combat itself can't be
  split further than "one PC's turn at a time" (an active `encounter`
  is a single object in `state/`), so each trial has to run to
  completion once started. What you *can* interleave is the framing:
  run two or three rounds of the fighter's duel, cut away ("while
  that's happening, what is the rogue seeing at their door?"), run a
  few rounds of the rogue's vault, cut back. Nothing in `state/` stops
  you narrating out of strict real-time order — the engine only cares
  about the order you issue commands in, not the order the fiction
  implies.
- **One shared clock, four separate outcomes.** Because Beat 11 is a
  single unsplit travel, all four trials are happening "at the same
  time" in fiction regardless of the order you resolve them at the
  table. Don't let a PC who finishes early retcon their way into
  helping another door — the wards seal against exactly that ("abides
  a single heartbeat"), and mechanically the map only has one
  `pc_spawns` entry to seat them on anyway.
- **Rest is also splittable.** If a trial goes badly and a PC needs to
  recover before their door (or after it, before rejoining), `engine
  rest --type short --pcs <pc-id>` rests just that PC without forcing
  a short rest on everyone waiting in the ward-hall.
- **No mid-encounter equip games.** `engine equip`/`unequip` block
  armor swaps mid-fight and cap one gear swap per PC per round even
  outside combat gating; don't try to have the fighter equip
  `doubtwhisper` *during* the duel that drops it — the item doesn't
  exist in their inventory until `encounter end` resolves loot into the
  party stash.

## Act 3 Reward Table

| Ward (solo encounter)       | Guardian                    | Item (yield)          | Item boon | XP (solo participant only) |
|------------------------------|------------------------------|------------------------|-----------|------|
| Duelist's Ward (fighter)    | Ward-Captain's Echo (x1)    | `doubtwhisper` (275 gp value) | weapon, `bonus: {attack: 1, damage: 2}`, **cursed**, grants `oath_whisper` | 350 |
| Latch-Vault (rogue)         | The Latchwight (x1)         | `hushstep_boots` (180 gp value) | gear, grants `silent_step` | 300 |
| Judgment Ward (cleric)      | The Unshriven Judge (x1)    | `oathlight_talisman` (150 gp value) | gear, grants `blessed` | 350 |
| Bound Ward (wizard)         | The Bound Sentinel (x1)     | `wardglass_lens` (200 gp value) | gear, grants `shielded` | 320 |

**No flat quest-completion xp grant this act** — unlike Reeve Halda's
bonuses in Acts 1-2, the four relics stand in for that bonus entirely.
The xp column above is ordinary `engine encounter end` monster xp, and
because each encounter is solo (`--pcs` seats one PC), the *entire*
total goes to that one PC rather than being divided by party size —
worked math is in each bestiary file's `notes:`.

Per-PC effect: each PC who runs their own class's trial gains only
that trial's xp — there is no world in which one PC runs all four (the
wards are class-keyed and self-excluding), so no single character's
total moves by more than ~350 xp. Starting from the Act 2 cumulative
of 3300 xp/PC, the worst case (350 xp) lands a PC at 3650 — nowhere
near the level-5 threshold (`xp_thresholds: {5: 6500}`) and nowhere
near `max_level: 5`. This act is explicitly not a leveling engine; it
is a gearing-up interlude between Act 2's ending and whatever the table
runs next.

**Getting the relic into the PC's hands.** `engine encounter end`
resolves monster loot into the shared `party` stash (see
`ttrpg_engine.combat.end`), same as every encounter in this adventure —
it does not know or care that only one PC was present. Because these
are solo fights, follow every `ward-<class>` encounter's `end` with an
explicit `engine item add --actor <pc-id> --item <relic-id>` to place
the relic in the hands of the PC who actually earned it (the party
stash has no other PC who could plausibly claim a single-heartbeat
relic anyway). `engine equip --actor <pc-id> --item <relic-id>`
afterward puts its `bonus`/`grants_effect` into effect immediately.
