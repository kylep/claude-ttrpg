---
name: gm-combat
description: Use when combat starts in a claude-ttrpg session - runs the encounter loop through engine commands.
---

# Running combat

1. `engine encounter start <map-rel>` — read back the initiative order.
   `<map-rel>` is relative to `canon/` (e.g. `maps/encounters/road-ambush.yaml`).
2. Render every round start: `engine map render --svg`. If a viewer is
   running (`engine serve`), the live map is already on-screen — just
   point the operator at it and skip pasting ASCII into chat. Otherwise
   show the ASCII map in a code block. Note: the player web lens strips
   fenced code blocks from the story feed (an ASCII map shows hidden
   monsters and true positions), so a pasted map is GM-facing only.
3. On each turn (order comes from `engine encounter next`):
   After `engine encounter start`, the first combatant in the order is
   already up — run their turn before the first `engine encounter next`.
   - **PC (human player)**: ask for their action; execute it via
     engine commands; narrate the JSON result.
   - **PC (simulated) / monster**: choose a tactically sensible action
     (attack in range; else move toward the nearest threat using
     `engine move`, then attack if now in range), execute, narrate.
   - Attacks: `engine attack --attacker X --target Y [--adv|--dis]`.
     Apply --adv/--dis per the effects on either side (see the game's
     effects.yaml impact notes). The engine already enforces prone,
     hidden, grappled, restrained, and unconscious (the result's
     `adv_from`/`dis_from` lists say what applied) — only pass flags
     for GM-adjudicated effects like blessed or frightened.
   - Spells: `engine cast --caster X --spell s [--target Y | --at X,Y]`.
   - Line of sight: walls block attacks and spells (`no_los` error).
     `engine sight --actor X --target Y` answers "can X see Y, and how
     far" before you commit to an action.
   - Movement: `engine move` charges the cheapest route (walls and
     living hostiles block, difficult terrain costs +1 per cell,
     prone creatures crawl at double cost). `engine stand` gets up.
   - Stealth: `engine hide --actor X` (fails with `seen` unless every
     hostile's line of sight is blocked, and with `held` while grappled
     or restrained; rolls stealth). The roll takes disadvantage from
     equipped `stealth_dis` armor and advantage from the `silent_step`
     effect, automatically. Movement on either side is contested — a
     hidden creature moving into a watcher's sight, or a hostile
     rounding the cover, checks passive perception vs the stealth roll
     (`revealed_by`/`spotted` in the move result). Attacking or casting
     from hiding grants advantage and then reveals.
   - Grappling: `engine grapple --actor A --target B` (contested;
     grappled creatures cannot move or take off), `engine escape
     --actor B`, `engine grapple ... --release`, and `engine shove
     --actor A --target B` to knock prone.
   - Poisoned/frightened: apply via `engine effect add`; the engine
     rolls the sufferer's attacks, checks, and contests at
     disadvantage. Give frightened a `--source <cid>` and it only
     bites while that combatant is alive and in view — and the victim
     cannot willingly move closer to it.
   - Darkness: `dark` terrain cells (or a map-wide `dark: true`) hide
     whoever stands in them unlit — attacks against them take
     disadvantage, attacks by them gain advantage, and they can
     `engine hide` with no cover. An equipped torch grants `lit`,
     which cancels all of it; monsters get light via
     `effect add --name lit`.
   - Flying: `engine ascend` / `engine land`; a flyer forced down takes
     fall damage automatically (dropped to 0 hp aloft, or its flying
     effect removed/expired). `engine fall --actor X [--dice 2d6]` for
     GM-ruled falls off ledges and the like.
   - Sneak attack is automatic for combatants with the `sneak_attack`
     feature — never add it by hand; the result reports `sneak_attack`
     when it applied.
   - Gear swaps cost the turn's action — the engine enforces one non-armor
     `engine equip`/`unequip` per combatant per round and blocks armor
     entirely mid-encounter (GM can override with `--force`).
   - Consumables: `engine item use --actor X --item healing_potion
     [--target ally]` rolls the item's own heal/damage/effect, applies
     it, and decrements the stack — never resolve a potion by hand.
     Targets other than the drinker must be adjacent and on the same
     plane; it shares the once-per-round gear action.
4. A PC hitting 0 HP starts death saves: `engine deathsave --actor X`
   on each of their turns until revived, stable, or dead.
5. Combat ends when one side is dead, surrendered, or fled:
   `engine encounter end` — report xp and loot from its JSON.
6. Never move a token, change HP, or decide a hit outside the engine.
7. Narrate for the room, not the spreadsheet. Players may be reading the
   player web lens, which hides monster HP behind words
   (healthy/wounded/bloodied) and hides hidden enemies entirely. Keep
   exact enemy HP and hidden-enemy positions out of player-facing prose
   — describe a wound, don't quote the number. Engine JSON and the GM
   lens carry the real figures.
