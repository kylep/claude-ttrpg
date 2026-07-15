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
5. Offer character creation: for each PC run
   `engine char create --name ... --class ... --race ... --assign ... --skills ...`
   (standard array 15,14,13,12,10,8; `--skills` takes exactly the class's
   `skill_choices` count — 2 for most classes, 3 for the rogue — chosen
   from that class's `skills` list, both in its ruleset file. Passing the
   wrong number fails with `bad_skills`.) Commit: `git commit -am "party created"`.
6. Remind the operator: sessions start with the gm-session skill;
   save points are `git tag`; forking a timeline is `git branch` from
   any tag or commit (branches never merge).
