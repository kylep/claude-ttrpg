# Post-v1 backlog

From the v1 final review (2026-07-13). Items the review dispositioned as
fix-later; none block play.

## Engineering

- **Portable game path in `world.yaml`** — the manifest stores an absolute,
  machine-local path to the game; worlds break if cloned to another machine.
  Support a repo-relative or registry-style reference.
- **Wire ruleset tunables the engine hardcodes** — `core.yaml` declares
  `crit_on`/`fumble_on`, `combat.yaml` declares initiative die/attr and
  `diagonal_cost`, `recovery.yaml` declares death-save DC/counts, but the
  engine hardcodes all of them. Either honor the values or mark the fields
  descriptive-only.
- Dice expression bounds (`999999d6` allocates a huge list) — cap count/sides.
- `init_world` leaves partial `canon/` behind on failure; retry requires a
  manual clear. Consider cleanup-on-failure.
- Monster deaths emit no `death` timeline event (PCs get one); add on
  `dead: true` for a self-contained audit log.
- `encounter end` grants XP to dead PCs; `xp grant` skips them — pick one.
- Escape encounter/combatant names in SVG output (`xml.sax.saxutils.escape`).
- `session-end` skill: `grep "session: N"` substring-matches 1 vs 1x — anchor it.
- Shared `resolve_hit()` for the nat-1/nat-20 formula duplicated in
  `combat.attack` and `spells.cast`; drop unused `worldfs` import in spells.py.
- Small test gaps: chargen error paths, `grant_xp` dead-skip, `bad_coord`,
  adv/dis/crit branches of `check`; e2e map assertion is trivially true
  (legend always contains `#`) — assert grid rows instead.
- `--actors` comma-split doesn't strip whitespace.
- `render.symbols` needs a bounded fallback if an encounter ever has >26
  same-case same-initial combatants.

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
