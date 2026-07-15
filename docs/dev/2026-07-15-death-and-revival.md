# Death, XP, and revival (2026-07-15)

The ruling for what happens to a PC that dies, and how it can come back.
Resolves the backlog's "encounter end grants XP to dead PCs; xp grant skips
them — pick one" and adds a revival path. Based on D&D 5e (Raise Dead /
Revivify) trimmed to fit this engine's categorical effect model, with an eye
to comparable systems (a return-with-a-toll, not a free rewind).

## XP: the dead still earn it

XP is awarded to the PCs who were **in the fight**, alive or dead. A hero
that fell mid-encounter earned that xp and keeps it. Concretely:

- `encounter end` grants xp to every participant (`enc["pcs"]`), including any
  that died during it — unchanged, now the documented intent.
- `level.grant_xp_to` (behind `engine xp grant` and quest rewards) no longer
  skips dead members. (Quest *completion* still refuses a dead recipient —
  a corpse can't turn in a bounty — but that's a separate gate.)

So a revived PC is never behind on xp for awards made while it was down.

## Revival: `engine revive`

`engine revive --actor X [--hp N]` restores a dead PC to life.

**What the engine enforces (mechanics only):**

- The target must currently be `dead` (else `not_dead`); must be a PC (else
  `not_a_pc`).
- It clears `dead`/`dying`/`unconscious` and any death-save tally.
- It returns at `--hp` (default **1** — on death's door, like Revivify /
  Raise Dead bringing you back at low HP).
- It applies **`weakened`**: engine-enforced disadvantage on the PC's
  attacks, checks, and contests (via `self_dis_conditions`) until it
  finishes a **long rest**, which clears it. This is the toll of dying —
  a lighter, engine-native stand-in for 5e's stacking −4 that lessens per
  rest. XP and level are untouched.

**What the engine deliberately does NOT enforce (world fiction):**

- *Whether* revival is available, and its cost. The engine performs the
  mechanical revival on command; the GM decides the fiction — a temple's
  fee (charge it with `engine gold spend`), a priest's spell, a rare
  potion, a scroll — and gates access accordingly. This is why the command
  takes no item or spell requirement: worlds use it however they like.
- Failure chances, time limits, or level/CON loss (older-edition style). A
  world wanting those adjudicates them narratively and applies the outcome
  through normal engine commands.

## Why this shape

The engine's effect model is categorical (advantage/disadvantage, on/off
conditions), not a numeric-modifier system, so a stacking −4 penalty would
be a poor fit. `weakened` = disadvantage-until-long-rest is meaningful,
enforced, and self-clearing, and it reuses the exact machinery poisoned and
frightened already run through. Keeping availability/cost in the GM's hands
matches the project's split: the engine owns math and state, the GM owns
fiction and rulings.
