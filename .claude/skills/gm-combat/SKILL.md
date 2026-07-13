---
name: gm-combat
description: Use when combat starts in a ky-ttrpg session - runs the encounter loop through engine commands.
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
     effects.yaml impact notes).
   - Spells: `engine cast --caster X --spell s [--target Y]`.
4. A PC hitting 0 HP starts death saves: `engine deathsave --actor X`
   on each of their turns until revived, stable, or dead.
5. Combat ends when one side is dead, surrendered, or fled:
   `engine encounter end` — report xp and loot from its JSON.
6. Never move a token, change HP, or decide a hit outside the engine.
