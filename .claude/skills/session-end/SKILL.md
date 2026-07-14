---
name: session-end
description: Use when the operator ends a claude-ttrpg session - writes the summary, reconciles canon, prunes dead lore, commits.
---

# Session end — the dreaming pass

Work through all steps; the final commit is the formal session boundary.

1. **Summary.** Write `sessions/session-NNN/summary.md`: 10-20 bullet
   beats, party status line (location, date, HP, level, notable loot),
   open threads. Source: the transcript file plus `timeline/` events
   from this session (`grep -l "session: N" timeline/*.yaml`).
2. **Canon diff.** `git diff <session-start-commit> -- canon/` (the
   commit made by gm-session). Read every changed file end to end.
3. **Reconcile.** Fix contradictions and plot holes the session
   introduced (an NPC in two places, a fact stated both ways) by
   editing `canon/` directly. Autonomy rule: fix and report — do NOT
   ask permission, but list every fix in your end-of-session report to
   the operator. Escalate (ask, don't fix) only when a fix would alter
   something load-bearing: a PC's history, a quest outcome, anything a
   player explicitly cared about.
4. **Prune.** Remove canon detail that will never matter again
   (the fifth description of the same corridor, one-off flavor NPCs
   with no thread attached). Compress to a line rather than delete
   when unsure. Git history keeps everything recoverable.
5. **Never touch** `state/` or `timeline/` in this pass. If step 3
   found a mechanical inconsistency, log it:
   `engine override log --summary "dreaming: <issue>"` and tell the
   operator — the fix is theirs to make next session.
6. **Commit** everything as one commit:
   `git add -A && git commit -m "session NNN: <one-line summary>"`.
7. Report to the operator: the summary, every reconciliation made,
   everything pruned, anything escalated — and, if `feedback.md`
   gained entries this session, list them and remind the operator to
   feed them back to the claude-ttrpg repo (they are engine/skill
   issues, not world canon; leave the file in place).
