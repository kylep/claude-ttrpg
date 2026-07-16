---
name: gm-session
description: Use when starting or resuming a claude-ttrpg play session in a world repo.
---

# Session start / resume

1. Confirm you are in a world repo: `engine state get session` works.
   Then run `engine world upgrade --check`: if it reports `outdated`, tell
   the operator the world's GM skills are behind the engine and offer to
   run `engine world upgrade` (it re-syncs `.claude/`; because the world is
   a git repo you commit the change as its own save point, and it's
   reversible). Never upgrade mid-session without asking. `no_kit`/`unknown`
   status is fine — just proceed.
2. Read `world.yaml`, `state/party.yaml`, `state/clock.yaml`, every
   sheet in `state/party/`, `house-rules.md` if it exists (the operator's
   standing table rules — they bind you all session; see gm.md), and the
   latest `sessions/session-*/summary.md` if one exists.
3. **Session zero** — if `state/party.yaml` has no members, build the
   party before anything else with the `party-create` skill: it walks
   each PC through race, class, stats, skills, and a short interview
   (the operator can hand any character off with "you figure it out"),
   builds every sheet, and commits "party created". PCs the operator
   didn't claim are yours to play. Don't open the scene until the party
   exists.
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
   with the first beat of `canon/adventure.md`. Post the opening to the
   story log before you say it (see gm.md, "The table record"):
   `engine story scene --title <location> --subtitle "<in-world date>"`,
   then the opening prose via `engine story narrate --text -` (heredoc),
   and `engine story reveal --npc <id>` for anyone on stage.
10. After opening, give the operator a short **"what you can do right
    now"** list grounded in the current state — the NPCs and hooks
    present in this scene, quests on the board (`engine quest list`), the
    exits out of this location (`canon/maps/region.yaml` edges), and the
    standing options (rest, shop, gear prep, split the party with
    `--pcs`). Post the same menu with `engine story choices --item ...`.
    A new player should always see their menu without having to ask for
    it; refresh it whenever the party arrives somewhere new.

Ending a session is the session-end skill — never improvise it.
