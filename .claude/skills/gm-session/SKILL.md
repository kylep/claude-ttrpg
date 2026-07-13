---
name: gm-session
description: Use when starting or resuming a ky-ttrpg play session in a world repo.
---

# Session start / resume

1. Confirm you are in a world repo: `engine state get session` works.
2. Read `world.yaml`, `state/party.yaml`, `state/clock.yaml`, every
   sheet in `state/party/`, and the latest `sessions/session-*/summary.md`
   if one exists.
3. `git status` must be clean. If not, stop and ask the operator.
4. Run `engine session start`. Note the session number N.
5. Create `sessions/session-NNN/transcript.md` with a heading and the
   in-world date; append notable beats to it as play proceeds (bullet
   lines, not verbatim chat).
6. Commit: `git add -A && git commit -m "session NNN start"`.
7. Recap the previous summary to the players in 3-5 sentences, state
   the party's location and date, then open the scene.

Ending a session is the session-end skill — never improvise it.
