# The Thornbury Quest Board

A weathered plank the length of a door leans against the moot-hall's
south wall, notched all over from a generation of nailed-up notices —
lost livestock, lost tempers, and the odd reward for a lost husband
nobody's looking very hard for. Reeve Halda tolerates it because half of
Thornbury's business gets done in front of it anyway, in the queue for
the well across the lane. Two notices are pinned there when the party
first walks into Thornbury: see `adventure.md`'s "Side Quests" section
for exactly when to post them.

Both quests below are independent of Reeve Halda's barrow contract and
of each other. GM setup commands assume the party has not yet left
Thornbury, so the world clock still reads `1203-04-17 09:00`
(`games/reference/game.yaml`).

## Quest A — "Find Tuffles" (npc, deadline)

> **FOUND: NOTHING. LOST: ONE PIG.**
> My prize sow Tuffles broke through the north fence three nights back
> and hasn't been seen since. Last tracks pointed toward Barrow Woods,
> may the Moot forgive me for saying it plain. She answers to her name
> and to a rattled bucket of slops. Bring her home — alive, mind,
> ALIVE — and I'll pay what I can spare, plus a little something a
> cleric left with me for emergencies.
> — Farmer Tobin, the north field past the mill

Giver: **Farmer Tobin** (`content/npcs.yaml`, holdings seeded with 20 gp
and 1x `healing_potion`). Reward escrows from his holdings at offer
time — modest gold plus the potion, exercising both gold and item
escrow at once. Deadline is exactly one year out from the campaign's
start date (`1203-04-17` → `1204-04-17`, this game's calendar being 12
months of 30 days per `engine/src/ttrpg_engine/clock.py`); `--deadline-hour`
is left at its default (9), which already matches the campaign's start
hour.

```
engine quest offer --title "Find Tuffles" \
  --desc "Farmer Tobin's prize sow Tuffles has gone missing toward Barrow Woods; he wants her found alive." \
  --giver npc:farmer_tobin --gold 15 --items healing_potion \
  --deadline 1204-04-17
```

Resolution spread — the GM picks one when the party finds Tuffles (or
doesn't):

- **Found alive and unhurt.** She's rooting in the scrub at the woods'
  edge, no worse than muddy and pleased with herself.
  ```
  engine quest accept find-tuffles --pcs <pc-ids>
  engine quest complete find-tuffles
  ```
  Tobin's 15 gp and his potion pass to the party as written.
- **Found alive, but off.** Physically fine, but she's gone quiet —
  long stretches staring back at the barrow line, and she doesn't
  startle at anything anymore. Tobin is thrilled and pays in full
  regardless (same `accept`/`complete` as above); the GM banks the
  detail as a future hook. Something in the Barrowdeep's wake touched
  her and didn't need to be hostile to leave a mark.
- **Found dead.** Goblins, a barrow hound, or plain bad luck got to her
  first. Tobin does not want to pay for that news.
  ```
  engine quest cancel find-tuffles
  ```
  The 15 gp and the potion refund to Tobin untouched, and the notice
  comes down without a reward changing hands.

## Quest B — "The Graveyard Risings" (world, indefinite)

> **THE YARD WON'T LIE STILL**
> Word to any sword, spell, or steady nerve for hire: about once a
> week, something claws up out of Thornbury's own graveyard — always
> the one, never more, and always at night. The Moot's dug it back
> down four times now and buried the story along with it, but a fifth
> grave won't stay quiet on its own. Whoever puts a stop to it — for
> good, not just for a week — names their own reward.
> — posted by order of the Moot

Giver: **world**, no funding NPC — the reward spawns fresh on
completion, and only a world-giver quest may do that or grant xp. No
`--deadline`: this is a standing hook the campaign never forces a clock
on, and it can be picked up and returned to at any point in the
campaign.

```
engine quest offer --title "The Graveyard Risings" \
  --desc "Something in Thornbury's own graveyard raises a lone walking corpse about once a week; find the cause and stop it for good." \
  --giver world --items graveward_coin --xp 50 --spawn
```

The lone corpse each rising sends up is a **Grave-Walker**
(`content/bestiary/grave_walker.yaml`) — run it on
`maps/encounters/graveyard.yaml`, which is *always* a solo spawn; there
is never more than one. If the party stakes out the yard at dusk
*before* a rising (rather than answering one), run
`maps/encounters/lych-gate.yaml` instead: the fresh Grave-Walker plus
the **Lych-Crake** (`content/bestiary/lych_crake.yaml`), the carrion
bird that has been getting fat on the risings. The gate wall screens
the party's approach — nobody has line of sight to the spawns, so a
stealthy PC can `engine hide` before anything moves — and the old
yew's dusk shadow (`terrain: dark`) is the campaign's first darkness:
anyone standing in it unlit can hide with no cover at all and is
attacked at disadvantage, while a lit torch (`engine equip` grants the
`lit` effect) cancels the shadow's protection both ways. The crake is
also the campaign's first flyer: see its bestiary `notes:` for the
swoop-loop turns and the three counters (shoot it down for a 2d6 fall,
ready for its landings, or grapple it grounded so it cannot take off).
The cause is **the Hollow Sexton**
(`content/bestiary/hollow_sexton.yaml`), a lonely, over-literal
grave-spirit whose ward has gone untended for a generation — sympathetic
enough that kill, scare, and parley are all meant to be real options at
the table. If the party tracks it down and talks fail, run
`maps/encounters/graveyard-vigil.yaml` instead of another Grave-Walker
fight.

However it ends, the GM completes the quest for whoever solved it:

```
engine quest accept the-graveyard-risings --pcs <pc-ids>
engine quest complete the-graveyard-risings
```

This materializes one `graveward_coin` into the first-named recipient's
inventory (`engine equip` to put its `gravewarded` effect into play) and
grants 50 xp to every named recipient in full — see `docs/design.md`'s
"Quests" section for why a world-giver quest is the only kind that can
do both at once.
