---
name: scene-banners
description: Use when opening a session, starting a scene, or when the party first arrives somewhere — to decide whether to show that place's cover/banner image.
---

# Scene banners — when to show location art

Some places carry cover art (a "banner") — a chapter-splash image meant to be
shown to the players. The DATA decides what has a banner; this skill decides
WHEN to surface it during play. If a place has no banner, there is simply
nothing to show, and that is fine.

## Where banners come from (deterministic)

A location declares its banner in content, and the engine resolves it fail-open:

- A world-map place: the `banner:` field on its node in `maps/region.yaml`
  (e.g. Millbrook → `art/banners/millbrook.png`).
- A town sub-map: the top-level `banner:` in `maps/<town>.yaml`.

The live viewer (`engine serve`) already shows a place's banner on its location
card automatically — click/open that location and the cover is there. Your job
is the narration timing.

## When to show it

1. **Session / campaign open.** Before the first scene of the very first
   session, present the starting town's banner as the chapter-one splash, then
   narrate the opening.
2. **First arrival.** The first time the party reaches any place that has a
   banner, show it as they come into view, then describe the scene.
3. **Optional set-pieces.** A major location or reveal with its own banner can
   get the same treatment when the party first sees it.

Show a given banner **once** — on first arrival (or if a player asks to see it
again) — not every visit. Never invent or generate a banner mid-session just to
have one; only surface art that already exists in the content.

## How to show it

- If the operator has the live viewer open (`engine serve`), just point them at
  the location card — the banner is already rendered there.
- Otherwise present the image at its content path (the `banner:` value, e.g.
  `content/art/banners/millbrook.png`) however your interface displays images.

See the `image-gen` skill only if the operator explicitly wants to CREATE new
banner art; showing existing banners never needs it. When you do create banner
art, image-gen's "House style" note is the guide: the evocative, painterly
"old road" look — warm light, storybook mood — is the house style for scene
banners.
