---
name: gm-combat
description: Use when combat starts in a claude-ttrpg session - runs the encounter loop through engine commands.
---

# Running combat

1. `engine encounter start <map-rel>` — read back the initiative order.
   `<map-rel>` is relative to `canon/` (e.g. `maps/encounters/road-ambush.yaml`).
2. Render every round start: `engine map render --svg`; show the ASCII
   map in a code block. Tell the operator renders/index.html has the
   pretty version.
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
     hostile's line of sight is blocked; rolls stealth). Moving while
     hidden is contested against watchers' passive perception
     automatically; attacking or casting from hiding grants advantage
     and then reveals.
   - Grappling: `engine grapple --actor A --target B` (contested;
     grappled creatures cannot move or take off), `engine escape
     --actor B`, `engine grapple ... --release`, and `engine shove
     --actor A --target B` to knock prone.
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
4. A PC hitting 0 HP starts death saves: `engine deathsave --actor X`
   on each of their turns until revived, stable, or dead.
5. Combat ends when one side is dead, surrendered, or fled:
   `engine encounter end` — report xp and loot from its JSON.
6. Never move a token, change HP, or decide a hit outside the engine.
