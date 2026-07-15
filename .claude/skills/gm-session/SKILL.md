---
name: gm-session
description: Use when starting or resuming a claude-ttrpg play session in a world repo.
---

# Session start / resume

1. Confirm you are in a world repo: `engine state get session` works.
2. Read `world.yaml`, `state/party.yaml`, `state/clock.yaml`, every
   sheet in `state/party/`, and the latest `sessions/session-*/summary.md`
   if one exists.
3. **Session zero** — if `state/party.yaml` has no members, build the
   party before anything else. Ask the operator (one question, not an
   interview): how many PCs, which they will play themselves, and any
   concept they care about (name, class, race); offer to design the
   rest. Create every sheet with `engine char create` (standard array
   from the game's `core.yaml`, class skill picks). PCs the operator
   didn't claim are yours to play. If the operator already said all
   this in their opening message, don't re-ask — just build.
4. `git status` must be clean. If not, stop and ask the operator.
5. Run `engine session start`. Note the session number N.
6. Create `sessions/session-NNN/transcript.md` with a heading, the
   in-world date, and a "played by" line mapping each PC to its player
   (human or GM — carry this into the session summary so resumes know);
   append notable beats to it as play proceeds (bullet lines, not
   verbatim chat).
7. Commit: `git add -A && git commit -m "session NNN start"`.
8. Offer the table view once per session: run `engine serve` as a
   background process (Bash run_in_background) and give the operator
   both URLs — player lens at http://127.0.0.1:8787/ and GM lens at
   /gm. If the port is taken (`port_busy`), a viewer is already
   running from a previous session; just re-share the URLs.
9. Recap the previous summary to the players in 3-5 sentences, state
   the party's location and date, then open the scene. For a brand-new
   world there is nothing to recap: open at the game's start location
   with the first beat of `canon/adventure.md`.

Ending a session is the session-end skill — never improvise it.
