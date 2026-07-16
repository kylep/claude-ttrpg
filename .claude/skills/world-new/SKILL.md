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
3. Seed `<dir>/house-rules.md` — the operator's standing table rules, read
   at every session start (see gm.md). Start it with the default below and
   ask if they want anything else in it:

   ```markdown
   # House rules

   Standing table rules. The GM reads this at every session start and
   obeys it all session; only the operator edits it.

   - AI players defer to human players on one-way decisions and on
     trades or transactions, such as spending gold.
   ```
4. `cd <dir> && git init && git add -A && git commit -m "world created: <name>"`
5. Tag the pristine state: `git tag genesis`.
6. Build the party with the `party-create` skill — it walks each PC through
   race, class, stats, skills, and a short interview (reading the menu from
   `engine char options` and building each sheet with `engine char create`),
   then commits "party created". Invoke it now if the operator is ready; if
   they'd rather set characters up at the table later, skip it — session zero
   in `gm-session` runs the same wizard on the first launch.
7. Remind the operator: sessions start with the gm-session skill;
   save points are `git tag`; forking a timeline is `git branch` from
   any tag or commit (branches never merge).
