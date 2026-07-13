---
name: world-new
description: Use when creating a new claude-ttrpg world (campaign) from a game definition.
---

# New world

1. Ask (if not given): game to use (default `games/reference`), world
   name, directory to create it in.
2. `engine world init <dir> --game <game-path> --name "<name>"`
3. Install the GM agent and skills into the world so `claude --agent gm`
   works from inside it: copy `.claude/` from this repo (the directory
   containing `agents/gm.md` and the gm-* / session-end / world-new
   skills — walk up from the game path to find it) into `<dir>/.claude`.
   Skip if the world is being created inside this repo's tree.
4. `cd <dir> && git init && git add -A && git commit -m "world created: <name>"`
5. Tag the pristine state: `git tag genesis`.
6. Offer character creation: for each PC run
   `engine char create --name ... --class ... --race ... --assign ... --skills ...`
   (standard array 15,14,13,12,10,8; class skill lists come from the
   game's class files). Commit: `git commit -am "party created"`.
7. Remind the operator: sessions start with the gm-session skill;
   save points are `git tag`; forking a timeline is `git branch` from
   any tag or commit (branches never merge).
