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
