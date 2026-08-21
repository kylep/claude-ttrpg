# Opening Chapters — two ways to begin

The familyrpg campaign offers **two low-level starter villages**, either a fine
place for a green party to begin. Pick one at session zero (or let the table
choose), both are level-1 friendly and scary-but-beatable:

- **Millbrook** — a cozy inland mill-village on the West Road, with cellars,
  a runaway pig, and a fallen hero. The classic start. (Below.)
- **Tidewrack Cove** — a barnacled coastal smuggler-town a day's sail west of
  Kingsreach, with a tide-cave, a thieving gull, and a fouled channel. (Further
  down, "Tidewrack Cove — the Opening Chapter".)

They sit a short hop apart near Kingsreach (`content/maps/region.yaml`, nodes
`millbrook` and `tidewrack`), so a party can start at one and sail or walk to
the other as the campaign grows.

---

# Millbrook — the Opening Chapter

The starter chapter of the familyrpg campaign: a cozy-heroic farming village
with a few very different troubles a new party can pick from. Tone is
scary-but-beatable and kid-friendly — spooky like a ghost story, never grim.

- Town layout and nodes: `content/maps/millbrook.yaml`
- Townsfolk: `content/npcs.yaml`
- The world beyond: `content/maps/region.yaml` (Millbrook is the `millbrook` node)

## The opening — the tavern meetup

The party gathers at the **Travellers Tavern**, kept by nosy, warm-hearted
**Bess Tandy**. Classic start: you're all here, out of the weather, and there's
work on the board by the door. Bess pours the rumors and points newcomers at the
notice board on the town green.

**Scene banner:** open the very first scene by showing Millbrook's cover art
(`content/art/banners/millbrook.png`) — the chapter-one splash. See the
`scene-banners` skill for when to surface banners during play.

## The quest board (run these at session setup)

Three jobs. All escrow their reward from the giver's holdings in
`content/npcs.yaml` at offer time. Deadlines are left off (indefinite) — add one
with `--deadline YYYY-MM-DD` if you want time pressure.

**1. The Cellars Under the Mill** — the world quest (thread 1). Three people
point at it: Bess in the tavern, Mabon and Jory at the mill, and the board
itself. Giver of record is the town purse (Headwoman Aldith).

```
engine quest offer --title "The Cellars Under the Mill" \
  --desc "Something has moved into the old storage tunnels beneath Mabon's mill — rats, and worse behind them. Clear it out." \
  --giver npc:headwoman_aldith --gold 50 --items healing_potion,healing_potion
```

**2. Truffles the Runaway Pig** — the gag quest. Farmer Dobbin's prize pig.

```
engine quest offer --title "Truffles the Runaway Pig" \
  --desc "Farmer Dobbin's prize pig Truffles broke her fence and wandered off toward the fields. Bring her home ALIVE." \
  --giver npc:farmer_dobbin --gold 15 --items healing_potion
```

**3. The Fallen Hero** — the statue on the road. Doran Cobb pays because it has
his supply wagons stuck.

```
engine quest offer --title "The Fallen Hero" \
  --desc "The old bronze statue has toppled across the mill road and no one can shift it; wagons are stuck. Clear the way." \
  --giver npc:doran_cobb --gold 20 --items healing_potion
```

## The Trading Post — Doran Cobb's stock

Doran buys and sells at the list prices in `ruleset/items.yaml`. Predefined
frontier stock (a village store — nothing fancy):

- **Weapons:** dagger ×3, club ×2, handaxe ×2, spear ×2, quarterstaff ×2, sling ×2, shortbow ×1
- **Armor:** padded ×2, leather ×2, hide ×1, wooden_shield ×2
- **Gear:** torch (bundle), rope ×3, rations (plenty), healers_kit ×2, thieves_tools ×1
- **Consumables:** healing_potion ×2, antitoxin ×1, and one greater_healing_potion kept under the counter at a premium
- **"On order from Kingsreach" (sold out — a nudge east):** chain_shirt, longsword, anything better

## Thread 1 — The Cellars (the starter dungeon)

Down the mill trapdoor. Begins cozy, turns a little spooky. Suggested descent:
giant rats in the near tunnels → giant spiders in the webbed side-rooms → a
break in the wall where **kobolds** have dug up from the old mine workings below
→ something slimy (a gray ooze) in the deepest, wettest room. A party of four
level-1 heroes can handle it; scale by how many kobolds you spawn.

**Connective tissue** — the cellars tie the town together:

- The same kobolds are the ones who **shoved the statue over** (thread: The
  Fallen Hero) and who trouble the **Stonewatch pass** to the west (thread 4).
  Their tunnels connect down toward the mountain mines.
- The **hooded strangers** from the grave-hill (thread 3) can turn up meddling
  in the deepest cellar room, tying the cozy dungeon to the bigger shadow if you
  want the campaign to grow that way.

## The two board gags, in detail

**Truffles (secret):** Truffles is not really a pig. She is some important
person — a fugitive noble, a hiding wizard, a cursed knight, GM's choice —
**polymorphed** and lying low. Play her straight as a greedy, clever, escape-artist
sow; the truth only ever surfaces if you want it to (a spell breaks, she speaks,
someone recognizes an old signet on her collar). If she gets eaten by a wolf on
the way home, oh well — nobody in Millbrook is ever the wiser, and it stays a
funny story. The reference campaign's "found alive, but... off — keeps staring at
the tree line" ending is the seed if you'd rather leave a thread dangling.

**The Fallen Hero:** the heavy bronze statue can be cleared by muscle (a big
combined Athletics effort, or a lever and Doran's stuck wagon-team), by
cleverness (dig it a ramp, roll it on rope and logs), or by finding out **who
knocked it down** — which leads straight to the kobolds and thread 1. Watchman
Toft remembers the hero's name and will happily tell the tale.

## What's next — the Free Road (thread 2)

Once Millbrook is sorted, the natural way onward is **east along the Free Road to
Kingsreach**, the great free city — and that road is exactly where the trouble
starts: wagons robbed, goblins in the hedges, a bandit crew with a tough captain.
Frame thread 2 as "the road to the city, and the adventure that finds you on it."

## Points of interest (not quests)

- **The wet meadow** — boggy low ground a little way out, haunted by a floating
  trickster light (a will-o'-wisp) that leads travelers off the safe path.
  Notable loot: deep in the bog, on the bones of an adventurer the light drowned
  years ago, lie a pair of **boots_of_leaping** — perfect for crossing the very
  mud that guards them. Stirges and a giant frog or two make the wade dangerous.
- **The old grave-hill (thread 3 seed)** — southeast past the fields, an ancient
  burial mound the townsfolk call the Barrow-downs. Strange night-lights, the
  restless dead, hooded strangers, a missing shepherd. Spooky, not gross. This is
  the thread that can grow into the campaign's long shadow (toward Duskhold, and
  much later a lich) if the party keeps pulling it.
- **The Stonewatch pass (thread 4 seed)** — the west road to the dwarves is
  **gated**: only dwarves and gnomes pass freely; everyone else needs a soulbound
  **Friend of the Dwarves** token (`ruleset/items.yaml`). The pass has kobolds in
  the abandoned mine tunnels, wolves and boar on the trail, and a dwarven survey
  team that never came back. Going around by water is no good — the river runs
  fast, cold, and deadly.


---

# Tidewrack Cove — the Opening Chapter

The coastal alternative to Millbrook: a barnacled cliff-town clinging to a
hidden cove on the southern shore, a day's sail west of Kingsreach and off the
trade lanes — which is exactly why it has a smuggler problem. Wreck-divers,
tide-pools, and lights in the sea-cave at night. Same tone as Millbrook:
scary-but-beatable and kid-friendly, spooky like a ghost story, never grim.

- Townsfolk: `content/npcs.yaml` (the `location: tidewrack` entries)
- The world beyond: `content/maps/region.yaml` (Tidewrack is the `tidewrack`
  node, a packet-boat hop from Kingsreach)

## The opening — the Salt Kettle

The party arrives on the morning tide (off a fishing coaster, or on foot down
the cliff-stair) and ducks into **The Salt Kettle**, the harbor tavern, kept
by warm, sharp-eyed **Nessa Coble**. She pours chowder, trades rumors, and
points newcomers at the notice board nailed by the door. She is the party's
first friendly face and the softest nudge toward the sea-cave.

**Scene banner:** there is no painted banner for Tidewrack yet. Open on the cove
in words — gulls, the smell of salt and tar, the long wooden docks on their
green-slick posts — and generate one later with the `svg-art` / `image-gen`
skills if you want it.

## The quest board (run these at session setup)

Three jobs. Each escrows its reward from the giver's holdings in
`content/npcs.yaml` at offer time. Deadlines are off (indefinite) — add one with
`--deadline YYYY-MM-DD` for time pressure.

**1. Lights in the Tide-Cave** — the world quest (the starter dungeon). The
reeve backs it from the town purse.

```
engine quest offer --title "Lights in the Tide-Cave" \
  --desc "Strangers' lanterns burn in the sea-cave under the docks at low tide, and cargo goes missing on the nights they show. Find out who — and put a stop to it." \
  --giver npc:reeve_sula --gold 50 --items healing_potion,healing_potion
```

**2. The Gull King's Hoard** — the gag quest. Granny Winkle's problem.

```
engine quest offer --title "The Gull King's Hoard" \
  --desc "A huge, bold seagull the whole cove calls the Gull King has been snatching anything shiny — including Granny Winkle's late husband's brass compass. Get it back." \
  --giver npc:granny_winkle --gold 15 --items healing_potion
```

**3. The Fouled Channel** — the muscle-or-cleverness quest. Doff Keel's boats
are stuck.

```
engine quest offer --title "The Fouled Channel" \
  --desc "A wrecked skiff and a tangle of old nets block the cove mouth at low tide; no boat can pass. Clear the channel." \
  --giver npc:doff_keel --gold 20 --items healing_potion
```

## The Chandlery — Tam Rigg's stock

Tam Rigg buys and sells at the list prices in `ruleset/items.yaml`. A small
harbor chandlery — rope, tar, and the basics:

- **Weapons:** dagger ×3, club ×2, handaxe ×2, spear ×2, sling ×3, shortbow ×1
- **Armor:** padded ×2, leather ×2, wooden_shield ×2
- **Gear:** torch (bundle), rope ×4, rations, healers_kit ×2, thieves_tools ×1,
  a coil of net and a fishing hook or two for the clever
- **Consumables:** healing_potion ×2, antitoxin ×1
- **"Comes in on the Kingsreach packet" (sold out — a nudge east):**
  chain_shirt, longsword, anything fancy

## The starter dungeon — the Tide-Cave

Reached at **low tide** through the sea-cave mouth under the docks (at high
tide it floods — a natural clock and a natural danger). Begins cozy, turns a
little spooky. Suggested descent:

- **The shallows** — a giant_rat or two on the wet ledges (a gentle first
  fight), and a giant_frog lurking in a tide-pool that lunges if you wade.
- **The lantern-shelf** — where the smugglers work: one or two **kobold**
  diggers hauling crates, with a single **bandit** lookout. Can be fought,
  sneaked past, or **talked** past — the kobolds are hirelings and scare
  easily. A few **stirge** roost in the ceiling cracks and drop on torchlight.
- **The deep pool** — a pale **lure-light** hangs over black water at the
  cave's heart (a **will_o_wisp**). Play it as the Millbrook wet-meadow wisp: a
  trickster that lures the careless toward the drowning-deep, not a straight
  fight; it flees when faced boldly. On the ledge behind it, in the bones of a
  diver it lured down years ago, lies the reward for reaching this far (GM's
  pick from `ruleset/items.yaml` — a water-friendly trinket suits the place).

**Who is really behind it:** a smooth **bandit_captain** running contraband up
the coast for someone in Kingsreach, using Tidewrack because no one watches it.
Meet them as a person first (charming, generous with a coin), not a health bar.
If the campaign grows, the sea-devils (**sahuagin**) the smugglers have been
quietly buying off are the darker water the wisp only hints at — save them for a
level 2–3 party.

**Connective tissue** — the cave ties the town together:

- The same smugglers **fouled the channel** (quest 3) sinking a skiff to hide
  their night-work, and the **Gull King** (quest 2) has been stealing their
  dropped brass — his hoard holds a **smuggler's token** (a clue to who they
  answer to) as well as Granny's compass.

## The two board gags, in detail

**The Gull King (secret):** the Gull King is only a very large, very clever
gull — but his cliff-nest hoard is a magpie's treasure of the cove's lost
shinies, and among them is one thing that matters: a **smuggler's token** that
names who the contraband answers to. Get the hoard by climbing the cliff,
out-bribing a bird with something shinier, or a kind soul coaxing him — no
killing required, and funnier if avoided. If a player just wants to fight a
seagull, let them; it is a gull.

**The Fouled Channel:** the block clears by **muscle** (a combined Athletics
haul on the sunk skiff at dead low tide), by **cleverness** (cut the net-tangle,
float the wreck off on the rising tide, rig Doff's block-and-tackle), or by
**finding out who sank it** — which leads straight to the Tide-Cave and quest 1.

## Points of interest (not quests)

- **The tide-pools** — flat rocks west of the docks, full of darting crabs and
  one improbably chatty hermit crab a kind child might befriend (pure whimsy; a
  soft, safe wonder-beat between dangers).
- **The old wreck on the Teeth** — a merchantman broken on the rocks at the cove
  mouth, half-drowned at high tide. Loot in the flooded hold; **stirge** or a
  lone **sahuagin** scavenger make the wade dangerous. For the bold.
- **The Dark Light** — the cove's lighthouse stands **unlit**, and no one will
  quite say why the last keeper left. A slow-burning mystery seed that can grow
  into the campaign's long shadow (the sahuagin, and whatever they answer to out
  past the Teeth).

## What's next — the Kingsreach packet

Once the cove is sorted, the natural way onward is the **Kingsreach packet-boat**
east to the great free city — following the smugglers' contraband to whoever in
Kingsreach was paying for it. Frame the next chapter as "the trail of coin, and
the city at the end of it."
