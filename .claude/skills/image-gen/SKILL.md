---
name: image-gen
description: Use when the operator wants art generated for the game — illustrating a handbook, world guide, or bestiary/NPC entry, or one-off world/scene art — via tools/imagegen.py.
---

# Generate images

Drives `tools/imagegen.py`, a standalone script that calls OpenAI or Gemini
image models. Every image costs real money, so this skill runs a cheap
health check first and reports spend after every run — never skip either
step.

## 1. Health check

```bash
uv run tools/imagegen.py --ledger-status
```

This costs nothing: it just prints cumulative estimated spend and confirms
the script runs at all. Do this before composing prompts, not after.

## 2. If keys are missing or invalid

If a generation attempt reports a missing or invalid API key, the tool
exits 1 with a one-line message naming the env var (e.g. `Missing
OPENAI_API_KEY for provider 'openai'. Set it in .env (see .env.sample) or
export it before running.`). When that happens: **relay that message to
the operator verbatim and stop.** Do not retry, do not silently fall back
to the other provider, and do not attempt to read, guess, or generate a
key. Setup is:

```bash
cp .env.sample .env   # then edit .env and add OPENAI_API_KEY and/or GEMINI_API_KEY
```

## 3. Compose prompts

Keep one consistent style line for the whole session so a handbook or
world guide's art doesn't look like five different artists worked on it.
Suggested default — adjust to the game's actual tone if `canon/` or the
game's content establishes one:

> "painterly fantasy illustration, muted earth tones, ink-and-wash
> linework, no text or watermarks"

Append it to every subject-specific prompt, e.g.:

> "a goblin archer crouched in undergrowth, painterly fantasy
> illustration, muted earth tones, ink-and-wash linework, no text or
> watermarks"

## 4. Run the tool

```bash
uv run tools/imagegen.py --prompt "<subject + style line>" --out <path>
```

Override the provider for one run with `--model gemini` or `--model
gemini-2.5-flash` (default is `openai`, or whatever `IMAGE_MODEL` is set to
in `.env`). For several images in one invocation, use repeated
`--prompt`/`--out` pairs or `--batch prompts.json` (a JSON list of
`{"prompt": ..., "out": ...}` objects) — but respect
`IMAGEGEN_MAX_PER_RUN` (default 1): if the operator wants more art than the
cap allows, that's their call to raise it, not yours to work around by
running the tool in a loop without telling them.

## 5. Place outputs

- Reusable game art (bestiary, classes, items, region maps) → the game's
  own `content/art/` (e.g. `games/reference/content/art/`).
- World-specific or one-off scene art → the world's `renders/`.

Use descriptive filenames (`goblin_archer.png`, not `image1.png` or
`out.png`) — these are checked into the game/world repo alongside the
content they illustrate.

## 6. Report spend

After every run — success, partial, or refused — tell the operator:

- what was generated and where it was written,
- the per-image cost estimate and the running ledger total the tool
  printed, or
- the exact refusal message if `IMAGEGEN_MAX_PER_RUN` or
  `IMAGEGEN_SPEND_CAP_USD` blocked the run.

A cap refusal is the tool working as designed, not a bug — don't try to
route around it. Tell the operator the current ledger total and that
raising `IMAGEGEN_SPEND_CAP_USD` / `IMAGEGEN_MAX_PER_RUN` (in `.env` or the
environment) is their call.
