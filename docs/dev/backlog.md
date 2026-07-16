# Post-v1 backlog

From the v1 final review (2026-07-13). Items the review dispositioned as
fix-later; none block play.

## Engineering

Deferred, not blocking:

- **Structural refactors** (see `2026-07-15-refactor.md`): split
  `combat.py`/`cli.py` into packages; broaden `guard()` to map
  malformed-YAML `KeyError`/`TypeError`; a set of lower-value nits.
- **Wheel-bundling of the agent kit + games.** `engine world init`
  installs `.claude/` and resolves games from the repo tree, which works
  for the editable/dev install everyone uses. `uv_build` can't force-include
  files from outside the package dir, so a distributed wheel would need the
  kit copied into `src/ttrpg_engine/agent_kit/` and `.../games/` (a build
  step, blocked on not wanting two live copies of `.claude/`). Resolution
  already prefers a packaged copy if present.
- **Live-world skill upgrades.** Worlds snapshot skills at creation;
  `engine world upgrade` now re-syncs a world's `.claude/` with the
  engine's current kit (`--check` reports drift via a `.kit-version` hash;
  gm-session nudges when behind; the world is a git repo so the upgrade is
  a reviewed, reversible save point). Still open, same shape as
  game-version pinning: applying newer *game content* to a live world
  (`world upgrade --game`) pulls in state migration and isn't built.

## Decided (carve-outs, documented here)

- `engine game validate` failure emits `{"valid": false, "errors": [...]}`
  on exit 1 rather than the global `{"error": ...}` envelope — kept
  deliberately: the errors array is the command's payload.
- Rest/travel events are stamped with the post-advance clock (completion
  time), and initiative ties break by descending id — both accepted as
  deterministic-and-fine.

## Post-v1 features (per design.md)

- Insert-mode play + predestination validator (hard layer).
- Fork/save-management skill; never-merge enforcement hook for world repos.
- Region-map image generation from node coords/terrain tags.

## From the equipment / party-split round (2026-07-13)

- Effects are keyed by name only: an equipment-granted effect and a
  GM-applied effect with the same name clobber each other on
  unequip/set. Needs effect provenance if it ever matters in play.
- `engine item dispel` works on any effect-granting item, not just
  cursed ones (GM-only escape hatch; broader than the curse remedy it
  was specced as).
- `travel --pcs` naming the full roster leaves `party.location` stale;
  consider detecting full-roster moves.
- `level.grant_xp` still grants to all members regardless of splits;
  dead PCs never leave `party.members` (no retire/bury flow).
- Equipping monsters is unsupported (a monster id gets a clean `not_a_pc`
  error).

## From the tactics round (2026-07-14)

Carve-outs from the stealth/LOS/terrain/grapple/darkness work on the
`tactical-mechanics` branch; all deliberate, none block play.

- Sneak attack's "once per turn" is implemented as once per *round*
  (keyed on `enc.sneak_used[attacker] == round`); the engine has no
  reaction/off-turn attack concept to distinguish turns by.
- Active searching for a hidden creature stays GM-run (`engine check`
  with perception vs the stored stealth total, then `effect remove`);
  the automatic contests only cover incidental notice on movement.
- Walls block line of sight regardless of altitude — a flyer cannot
  see or shoot over a wall. Fine while walls are read as full-height;
  revisit if maps ever want low cover.
- `engine sight` reports geometric LOS and distance only; it ignores
  darkness and hidden. Good enough for GM adjudication, but it can say
  `los: true` for a target the attacker would roll at disadvantage
  against.
- `lit` is binary and personal: a torch-bearer illuminates only itself,
  not adjacent cells. No light-radius model.
- Darkness and conditions never touch saving throws (`_resolve_save`
  rolls raw); 5e agrees for darkness, less so for restrained vs DEX
  saves. Revisit if saves grow adv/dis support.
- Auto-fall triggers on `effect remove`/expiry of `flying`, but not on
  unequipping a hypothetical flying-granting item (no game ships one
  yet; wire `inventory.unequip` through the same path if one ever
  does).
- `restrained` has no engine-side applier (no net/web items or attacks);
  it's GM `effect add` only.
- Encounter-map terrain (including the new `dark` type) is still not
  validated by `game validate` — a typoed terrain type is silently
  ignored.

## From the live-viewer round (2026-07-14)

Carve-outs from `engine serve` (see docs/dev/2026-07-14-live-viewer-design.md).

- ~~The story pane parses Claude Code session transcripts~~ — resolved
  2026-07-16: the feed now reads the engine-written story log
  (`state/story.jsonl`); the transcript coupling (`story.py`) is gone.
- Session-history browsing: the full story log renders as one feed, but
  there's no per-session jump/filter UI.
- The game ruleset is loaded once at server start; a mid-session
  ruleset change needs a serve restart.
- When it is a hidden monster's turn, the player lens shows `up: ???` —
  players learn *something* acts, which is genuinely 5e-accurate but
  worth knowing.
- Each SSE client polls world mtimes itself (~300ms rglob) — fine for a
  table's worth of browsers, not for dozens.
- The `/renders/<name>` route (round-stamped GM battle-map history) has
  no lens gate — a spectator who hand-types `/renders/index.html` sees
  unfiltered GM maps. The player page never links it (its live map comes
  filtered through `/api/state`), so this is manual-URL-only on a
  localhost tool; lens-gate or drop the route if it ever matters.

## From the quests round (2026-07-13)

- Canon `npcs.yaml` gold/inventory shapes unvalidated by `game validate`;
  malformed entries raise a raw traceback instead of a JSON error.
- Quest gold-remainder goes to the first recipient in caller-supplied
  order; confirm or canonicalize.
- Escrowed items pay out to the first recipient only (documented; revisit
  if multi-recipient item splits ever matter).
