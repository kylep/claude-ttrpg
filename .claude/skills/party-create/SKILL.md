---
name: party-create
description: Use to build a claude-ttrpg party at session zero — walks the table through each PC's race, class, stats, skills, and a short interview. Covers the party only, not town/world NPCs.
---

# Party creation

A guided setup for the players' **party** — the PCs they'll run, including any
members the AI plays. It does *not* create town or world NPCs; those already
live in `canon/`.

**Principle: thorough but default-fast.** Walk every member through every step,
but lead each step with the recommended default so the operator can accept it
in one word ("yes"/"default"/"you pick") and only slow down where they care.
Never invent numbers — the menu and every sheet come from the engine.

## 1. Frame the table (one message, not an interview)

Ask together: how many PCs; for each slot, does a human play it or should you
(the AI) run it. If the operator already said this in their opening ("party of
four, I'll play a dwarf fighter, you build the rest"), don't re-ask — take it.

## 2. Load the menu once

`engine char options` → JSON for the pinned game: `standard_array`, `races`
(bonuses/speed/flavor), and `classes` (`hit_die`, `cast_attr`, `skills` +
`skill_choices`, `starting_gear`, `starting_gold`, `level1_spells`,
`recommended_skills`, `recommended_array`). Present *from this* — never from
memory or by reading ruleset YAML yourself.

## 3. Build each member

For a **human-played** PC, walk the steps; at each, state the default and offer
to change it:

1. **Race** — list the four with their bonuses, speed, and one-line flavor.
2. **Class** — list them with role/hit die, and for the chosen one show its
   `skills` (+ how many to pick), `starting_gear`, and any `level1_spells`.
3. **Attributes** — offer `recommended_array` for that class as the default
   ("STR 15, CON 14, … — use it, or assign the standard array yourself?"). If
   the class has no `recommended_array` (null), ask for the assignment.
4. **Skills** — offer `recommended_skills` as the default; the operator may
   swap for any others on the class list. Must be exactly `skill_choices`.
5. **Name.**
6. **Interview** — 3–5 short shaping questions, kept light: a one-sentence
   concept, a **bond** (someone/something they care about), a **flaw or fear**,
   **why they're here / a tie to another PC**, and one memorable detail. These
   are flavor for you to play them by — they don't change the sheet.

For an **AI-played** PC ("you figure it out"), make the picks yourself in
character — sensible race/class, that class's `recommended_array` and
`recommended_skills`, a name and a one-paragraph concept — and give the
operator a single-line "here's who they are". Don't make them approve it.

Create every member the same way:

```
engine char create --name "<name>" --class <class> --race <race> \
  --assign STR=..,DEX=..,CON=..,INT=..,WIS=..,CHA=.. --skills a,b
```

`--assign` must be the full standard array across all six attributes and
`--skills` exactly the class's `skill_choices` from its list, or the engine
rejects it (`bad_assign` / `bad_skills`).

## 4. Record bios + played-by

For each member write `canon/party/<pc-id>.md` — the interview answers (concept,
bond, flaw, ties, detail) and a `**Played by:** <human name | GM>` line. The
engine sheet holds the mechanics; canon holds the story, and the played-by line
is how `gm-session` knows whose turns to run.

## 5. Finish

Recap the whole party in a few lines (name, race/class, who plays them), then
commit: `git add -A && git commit -m "party created"`. Hand back to the
`gm-session` skill to open the first scene — do not open the scene here.
