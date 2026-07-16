# Worlds are git repos — saves, forks, and time travel

A world's entire save state is files in its own git repo, so git *is* the
save system:

```
world.yaml      # which game + version this world was created from
house-rules.md  # your standing table rules — the GM obeys, only you edit
state/          # the present: party, character sheets, positions, clock
canon/          # narrative truth: setting, history, NPCs, factions, maps
timeline/       # append-only event log — every roll's outcome, every
                #   mutation, one file per event, ordered by in-world date
sessions/       # per-session transcripts and summaries
```

`state/` is authoritative for "now"; `timeline/` is the audit trail and the
story's mechanical record. Only the engine writes to either — the GM
narrates from engine output and edits `canon/` for narrative facts.

## House rules

`house-rules.md` at the world root holds your standing instructions for how
the table runs — things like "AI players defer to human players on trades
and spending gold" or "no PC dies without a warning beat." The GM reads it
at every session start and it binds all session, ranking just below your
live word (operator > house rules > skills > GM judgment). It's yours: the
GM never edits it uninvited, `engine world upgrade` never touches it, and
because it's committed with the save it rides forks and resumes. It's
instruction the GM follows, not engine enforcement — hard mechanical gates
would be an engine feature.

## Saving

The GM skills commit at every session boundary (`session NNN start`,
`session NNN: <summary>`), so each session is a save point out of the box.
For a named save you can return to, tag it:

```bash
git tag before-the-tomb
```

## Loading / forking

Rewinding is branching. A fork is a full alternate timeline — the original
keeps existing and can be resumed:

```bash
git branch tomb-attempt-2 before-the-tomb   # fork from the save point
git checkout tomb-attempt-2                  # play the alternate line
```

Timeline branches never merge — two presents can't be reconciled into one.
Deep history is naturally shared: everything authored before the fork point
exists in both lines' ancestry.

## Inserting history (backfilling the past)

An *insert* is a session set in the world's past — a flashback that fleshes
out backstory without touching the present. Two rules make inserts safe:
they are **lore-only** (nothing an insert session does auto-changes
`state/` — the present's HP, inventory, and positions stay untouched), and
they must respect **predestination** (the past can't contradict established
canon: an NPC alive today can't die in your flashback).

To run one today, tell the GM at a session start:

> "This session is an insert — a flashback set 20 years before the
> campaign, when Halda first came to Thornbury."

The GM then plays the scene normally (dice and checks still go through the
engine) but records the outcomes as narrative history in `canon/`
(history.md, NPC entries) instead of mutating the present. If something from
the flashback *should* exist in the present — a buried item, a debt, a
grudge — you apply it explicitly: say "GM override" and the change lands
through engine commands with a logged override event. Because canon lives in
git, an insert committed before a fork point is inherited by every timeline
forked after it — deep history stays shared.

First-class insert tooling is post-v1 and not yet built: dated `timeline/`
events for insert sessions and a validator that mechanically blocks
paradoxes (see [design.md](design.md), Tier 3 — Timelines). Until then,
predestination is enforced only by the GM's discipline plus the session-end
reconciliation pass.
