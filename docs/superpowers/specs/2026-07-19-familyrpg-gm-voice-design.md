# familyrpg GM voice & accessibility — design

Date: 2026-07-19
Status: approved-pending-review
Workstream: 1 of 5 from the 2026-07-19 playthrough improvement list.

## Context

A family playthrough (the `family1` save, run with `claude --agent gm`)
surfaced a batch of improvements. They decompose into five independent
workstreams, each its own spec → plan → build cycle:

1. **GM voice & accessibility** — this spec.
2. Web UI: character sheet & economy (inventory, spell slots, gold, HP bars).
3. Combat clarity (roll transparency, terrain legend, visible wounds, formation).
4. Rules depth (thieves' tools gating, stat-tuning, regional quest board).
5. Roll-your-own dice (manual result input + toggle).

This spec covers **only workstream 1**: changes to GM instructions, game
content, and art direction. **No engine or web-UI code changes.**

## Problems (from the playthrough)

- Jargon a young reader doesn't know was used without explanation: "Reeve",
  "barrow", "palisade", and "iron rations" (the GM's coinage — the item is
  named `rations` and already described plainly).
- NPCs didn't introduce themselves by name.
- Clicking an NPC in the viewer showed no description — NPC records carry only
  `name`/`role`/`disposition`/`wants` (GM-only); there is no player-facing
  `description` field populated.
- A specific NPC (Pedlar Okko) wanted a described physical appearance on click.
- A declared marching order wasn't honored: the party asked an NPC to lead, but
  when the fight started other PCs were seated in front.
- Art: the "old road" banner landed well; the operator wants to lean into that
  evocative style and is fine spending on a paid image model.

## Design

### A. Universal GM craft → `.claude/agents/gm.md`

These are good practice for **any** world, so they live in the shared GM
persona (synced into saves via `engine world upgrade`). Add a short
"Naming & clarity" block to the "Voice at the table" section:

- **NPCs name themselves.** When an NPC first addresses the party, they say who
  they are in character ("Halda — I'm the reeve here").
- **Define a hard word the first time you use it**, in-world and in the same
  breath: a short appositive, not a glossary aside. A reeve is "the headwoman's
  law-keeper"; a barrow is "an old grave-mound." Prefer the plain word; when you
  reach for a fancy one, unpack it once.
- **Use an item's own description; don't invent jargon.** Narrate `rations` from
  its `ruleset/items.yaml` description ("a day's trail food"), not as "iron
  rations."
- **Every NPC you invent gets a one-line look.** When you introduce an NPC of
  your own, give a player-facing sketch of their appearance and manner and write
  it to `canon/npcs.yaml` as that NPC's `description:` so their viewer card is
  never blank. `wants` stays GM-only; `description` is what players may see.
- **Honor declared positions.** When the party sets a marching order or names
  who takes point, keep it consistent in narration and seat them that way when
  an encounter begins — don't silently reshuffle who's in front. (The mechanical
  grid-spawn-from-formation model is workstream 3; here it's a narration rule and
  a pointer to place PCs by the stated order when calling the encounter.)

### B. familyrpg young-audience tone → game property

The kid-reading-level tone is specific to familyrpg (not the `reference` game),
so it ships **with the game**, not in the universal persona.

- `games/familyrpg/game.yaml`: add `audience: young` and a one-line `tone:`
  string. **Risk:** confirm `engine game validate` tolerates the new keys; if
  the schema is strict, drop the keys and rely on `voice.md` alone.
- `games/familyrpg/content/voice.md`: a short GM-voice brief for this game —
  aim for roughly an 8–10-year-old's reading level, short sentences, concrete
  images, define any word a young child wouldn't know, keep threats
  scary-but-beatable and death soft. This is guidance the GM reads, not content
  shown to players.
- Wire-up: `voice.md` is copied into a new world's `canon/` at `world-new` time
  (alongside the other content), and `gm-session` step 2 reads `canon/voice.md`
  if present — mirroring how `house-rules.md` is read and obeyed each session.
  Authority order is unchanged: operator's live word > house-rules.md > voice.md
  > skills > judgment.

### C. Content — player-facing NPC descriptions

- Add a `description:` field (1–2 sentences: appearance + manner, jargon-free,
  kid-accessible) to **every** NPC in `games/familyrpg/content/npcs.yaml`. Keep
  `wants` GM-only. The viewer's player lens already forwards `description`
  (`_npc_card` in `viewer_data.py`), so this lights up click-an-NPC with no code.

### D. Art direction (direction only, no regeneration)

- Update the image-gen guidance (`.claude/skills/image-gen` and/or
  `scene-banners`) to name the evocative "old-road" look as the house style for
  scene banners, and flux-2-pro as the preferred model for hero scene art, with
  the existing `IMAGEGEN_MAX_PER_RUN` spend cap intact. No images are generated
  in this workstream.

### E. Backport to the live `family1` save

The `family1` save is a separate git repo created before these changes; content
copied at `world-new` time does not re-sync. So, as a final step:

- Add `description:` to each NPC in `family1/canon/npcs.yaml` — including the
  GM-invented `reeve_halda` and `pedlar_okko` (Okko gets the physical
  description the operator asked for).
- Add `family1/canon/voice.md` with the familyrpg voice brief.
- These are `canon/` edits (permitted for the GM) committed in the save repo as
  their own save point.

## Non-goals

Deferred to later workstreams, explicitly out of scope here:

- Showing item descriptions or full inventory in the web UI (WS2).
- A mechanical marching-order/formation model on the combat grid (WS3).
- Roll transparency feed, terrain legend, visible-wound property (WS3).
- Thieves' tools gating, stat-tuning at char creation, regional quest board,
  manual dice (WS4–5).

## Validation

Prose/content change — validation is light:

- `engine game validate games/familyrpg` stays green after the `game.yaml` edit
  (the gate on whether new keys are allowed).
- Spot-check in the viewer (`engine serve`, player lens): a Millbrook NPC card
  now shows its `description`.
- Optional content lint: a test asserting every familyrpg NPC has a non-empty
  `description`.
- Read-through of the `gm.md` additions for coherence with the existing
  "Iron rules" / "Voice at the table" sections.
