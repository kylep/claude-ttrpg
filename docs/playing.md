# Playing

How to create a world and play a session. This assumes the `engine` CLI is
installed — see the [README](../README.md#install) if it isn't.

## Create a world

Either ask Claude to use the `world-new` skill (which does all of the below
for you), or by hand:

```bash
# init writes the world files into a new directory
engine world init ~/ttrpg/saves/world1 \
  --game ~/gh/claude-ttrpg/games/reference --name "World One"

# install the GM agent + skills into the world (claude loads .claude/
# from the directory you launch it in)
cp -r ~/gh/claude-ttrpg/.claude ~/ttrpg/saves/world1/.claude

# make it a git repo: the commit is save zero, the tag a named restore point
cd ~/ttrpg/saves/world1
git init
git add -A && git commit -m "world created: World One"
git tag genesis

# play — the GM commits automatically at every session boundary from here
claude --agent gm
```

(`--game` takes any path to a game directory; use the absolute path unless
you're running from inside this repo.)

## Your first session

Once the GM greets you, just say what you want in plain language — there is
no command syntax to learn. A typical first prompt:

> New campaign. Party of four: I'll play a dwarf fighter named Borin —
> build him for me, then design a rogue, a cleric, and a wizard and run
> those three yourself. Auto-GM. Start the adventure.

The GM creates every sheet through `engine char create`, plays any PC you
didn't claim (in combat it takes their turns; out of combat they chime in
but follow your lead), and opens the first scene. On later launches,
"resume" (or just "let's play") picks up from the last session summary.

## Steering the GM

Four phrases steer the operator relationship with the GM at any time:

- **"GM override"** — apply an instruction as-is; it gets logged to the
  timeline.
- **"manual GM"** — every ruling (DCs, NPC reactions) is deferred to you;
  the engine paperwork keeps happening automatically.
- **"auto GM"** — hand rulings back to Claude.
- **"feedback: ..."** — log a gripe or suggestion about how the game
  *works* (engine, skills, UX) to the world's `feedback.md` and keep
  playing; plain complaints ("I don't like that the map...") get logged
  too. Engine crashes land there automatically via a hook. Feed the file
  back to this repo when it has content.

## What the engine enforces

Gear is live state: `engine equip` / `engine unequip` recompute AC and
attacks from what's actually worn, magic items carry boons (and sometimes
curses — `engine item dispel` is the remedy), consumables resolve through
`engine item use` (the potion's own dice, one bottle off the stack), and
the party can split: `travel`, `encounter start`, and `rest` all take
`--pcs` to act on a subset, with XP flowing only to the PCs who were
actually in the fight. Quests are first-class state too (`engine quest
offer/accept/complete/cancel/list`): NPC and PC rewards are escrowed up
front — no vaporware bounties — while world quests can spawn rewards and
grant XP. Thornbury's quest board ships with two.

Combat is tactically honest: walls block line of sight (and shots),
movement pays for the actual route through difficult terrain, and the
engine enforces the conditions the rules only used to describe — prone,
grappled, restrained, poisoned, frightened (of a specific enemy, until you
break line of sight), and hidden. `engine hide` starts a real stealth
contest against passive perception, dark terrain conceals whoever stands in
it unlit (torches grant `lit` and give you away), flyers fight from the air
and take fall damage coming down, rogues get their sneak dice applied
automatically, and `grapple`/`shove`/`escape` are contested rolls. Every
attack and check reports *why* it rolled with advantage or disadvantage.
