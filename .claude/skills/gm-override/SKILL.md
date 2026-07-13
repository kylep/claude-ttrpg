---
name: gm-override
description: Use when the operator says "GM override", "manual GM", or "auto GM" in a claude-ttrpg session.
---

# GM override handling

**"GM override" + an instruction**: apply exactly what the operator
said, then immediately log it:
`engine override log --summary "<what changed and why>" --actors <ids>`
If it changes mechanical state, make the change through engine
commands (`damage`, `heal`, `item add`, `move --force`, ...) so state
and timeline stay consistent — the override event explains the cause.

**"manual GM"**: switch modes. From now on, before any adjudication
(DC, ruling, NPC decision) ask the operator and use their answer.
Engine paperwork continues unchanged. Confirm: "Manual GM on."

**"auto GM"**: switch back to auto-GM. Confirm: "Auto GM on."

Never infer an override from tone or repetition — the operator must
use the explicit phrase.
