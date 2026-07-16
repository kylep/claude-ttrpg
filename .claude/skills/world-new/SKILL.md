---
name: world-new
description: Use when creating a new claude-ttrpg world (campaign) from a game definition.
---

# New world

1. Ask (if not given): game to use (default `games/reference`), world
   name, directory to create it in.
2. `engine world init <dir> --game <game-path> --name "<name>"` — this now
   installs the GM agent + skills into `<dir>/.claude` itself, so no manual
   copy is needed. (If `<dir>/.claude/agents/gm.md` is somehow missing —
   e.g. a bare wheel install with no bundled kit — fall back to copying
   this repo's `.claude/` into `<dir>/.claude`.)
3. `cd <dir> && git init && git add -A && git commit -m "world created: <name>"`
4. Tag the pristine state: `git tag genesis`.
5. Build the party with the `party-create` skill — it walks each PC through
   race, class, stats, skills, and a short interview (reading the menu from
   `engine char options` and building each sheet with `engine char create`),
   then commits "party created". Invoke it now if the operator is ready; if
   they'd rather set characters up at the table later, skip it — session zero
   in `gm-session` runs the same wizard on the first launch.
6. Remind the operator: sessions start with the gm-session skill;
   save points are `git tag`; forking a timeline is `git branch` from
   any tag or commit (branches never merge).
