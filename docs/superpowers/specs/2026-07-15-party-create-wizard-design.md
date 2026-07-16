# Party-creation wizard — design

A guided "new game" flow that walks the table through building their **party**
at session zero. Scope is the party only — the PCs the players will run,
including any party members played by the AI. It does *not* author town or
world NPCs; those already live in a game's `canon/`.

## Principle: thorough but default-fast

Every party member walks every step (race → class → attributes → skills →
name → interview) — nothing is auto-decided behind the operator's back — but
each step leads with a recommended default they can accept in one tap. Depth
when they want it, one keystroke away when they don't.

## Party members are PCs

An "NPC party member" is not a different kind of entity: it is a PC whose
**played-by** is the AI rather than a human. Mechanically identical — a full
sheet built with `engine char create`, living in `state/party/`. So there is
**no** engine NPC-sheet work; the only difference is who takes the character's
turns, a fact the wizard records so `gm-session` can carry it forward.

Per member, the operator chooses per slot:

- **Define it** → the full default-fast walk.
- **Hand it off** ("you figure it out") → the AI builds the whole character
  and gives a one-line "here's who they are". No per-character approval gate.

## Architecture

Two pieces, split along the engine's existing seam (engine = deterministic
executor, Claude = the conversational layer):

### 1. `engine char options` — new, read-only

Emits, as JSON, everything a wizard needs to present the pinned game's choices,
resolved from the ruleset so the skill never re-derives rules by hand (this is
the gap that produced the earlier `skill_choices` doc bug):

- `attributes`, `standard_array`
- `races`: `{bonuses, speed, description}`
- `classes`: `{description, hit_die, cast_attr, skills, skill_choices,
  recommended_skills, starting_gear:[{id,name,type,description}], starting_gold,
  level1_spells:[{id,name,level,description}], level1_features,
  recommended_array}`

`recommended_array` is a class-authored default spread: each class YAML gains an
optional `attr_priority` (a full permutation of the six attributes, most to
least important); `char options` maps the sorted standard array onto it
(highest score → highest priority). A class without `attr_priority` reports
`recommended_array: null` and the wizard falls back to asking. `recommended_skills`
is the first `skill_choices` of the class's skill list. Both are guaranteed to
be valid inputs to `engine char create`.

Read-only, stateless; runs inside a world (same as `char create`).

### 2. `party-create` skill — new, the orchestrator

Runs the conversation; computes nothing. Flow:

1. **Table setup** — party size; for each slot, human-played or AI-played.
2. Load the menu once: `engine char options`.
3. **Per member** — human-defined: walk race → class → attributes (default
   `recommended_array`) → skills (default `recommended_skills`) → name →
   interview (concept · bond · flaw/fear · why-you're-here / tie to another PC ·
   one memorable detail). AI-defined: the GM makes the picks in-character and
   states a one-liner. Either way, execute `engine char create`.
4. **Bios** — write each member's flavor + played-by to `canon/party/<pc-id>.md`
   (the engine sheet has no field for narrative). Interview answers land here.
5. **Finish** — recap the party, `git commit "party created"`, hand off to
   `gm-session` to open the scene.

## Wiring

- `world-new` step 5 and `gm-session` session-zero defer to `party-create`
  instead of hand-rolling `engine char create` calls.
- `docs/playing.md` "Your first session" points at the wizard.

## Out of scope (noted, not built)

- Town/world NPC authoring (a world-building concern, not party setup).
- Point-buy or rolled stats — standard array only, as the engine enforces.
- Fully-statted combatant *non-party* companions.
