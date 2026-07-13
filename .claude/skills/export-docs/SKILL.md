---
name: export-docs
description: Use when the operator wants printable/shareable copies of the game — a game handbook, world guide, and campaign book — optionally uploaded as Google Docs.
---

# Export printable docs

Produces three self-contained HTML documents and, if `gws` is working,
uploads each as a Google Doc. Falls back gracefully to local HTML if `gws`
isn't available — this must never be treated as a hard failure.

Exported HTML embeds the game's own authored text verbatim, so only export
games from sources you trust. As defense-in-depth the exporter escapes
author-controlled fields and strips script-capable HTML (`<script>`,
event-handler attributes, `javascript:` URLs, etc.) out of markdown-rendered
content, but this is not a substitute for trusting the source.

## 1. Render the three exports

From inside a world (uses `canon/` for content and the world's pinned
game for ruleset):

```bash
engine export game
engine export world
engine export campaign
```

Repo-side, with no world (uses a game's own `content/` + ruleset):

```bash
engine export game --game games/reference
engine export world --game games/reference
engine export campaign --game games/reference
```

Default output directory is `./exports/`; pass `--out DIR` to change it.
Each command prints `{"file": "<path>", "sections": N}` — collect the
three `file` paths.

## 2. Preflight gws

```bash
gws drive files list --params '{"pageSize": 1}'
```

If this fails for **any** reason (not installed, not authenticated, API
error, network) — **stop here**. Do not attempt uploads. Report the
three local HTML paths from step 1 as the printable fallback and tell
the operator gws wasn't available. This is the expected, graceful
outcome when gws isn't working, not an error to fix.

## 3. Upload each doc

Verified invocation (tested live against a real Drive account while
writing this skill — see note below on the `--upload` path restriction):

```bash
gws drive files create --upload <relative-path-to.html> \
  --params '{"fields": "id,name,webViewLink"}' \
  --json '{"name": "<Doc name>", "mimeType": "application/vnd.google-apps.document"}'
```

This both uploads and converts the HTML to a native Google Doc in one
call (the `application/vnd.google-apps.document` target mimeType with a
non-Docs source mimeType triggers conversion), and the
`--params '{"fields": ...}'` on the `create` call returns `webViewLink`
directly — no follow-up `get` needed.

**Path gotcha:** `gws --upload` refuses any path that resolves outside
the current working directory. `cd` into the exports directory (or
wherever the HTML files landed) before running the upload commands, and
pass a bare filename (or a path relative to that directory), not an
absolute path elsewhere in the tree.

## 4. Doc names

Use exactly these names (fill in the game/world specifics):

- `claude-ttrpg: Game Handbook (<game> <version>)`
- `claude-ttrpg: World Guide (<world or game name>)`
- `claude-ttrpg: Campaign Book (<world or game name>)`

## 5. Report

Report the three Doc links (`webViewLink` from each `create` response)
to the operator. If any single upload fails partway through, report
which docs succeeded (with their links) and which fell back to local
HTML — don't discard the ones that worked.

## Verification note

This skill's upload shape was verified live: uploaded a tiny test HTML
file, confirmed it converted to a real Google Doc (fetched via `gws docs
documents get`), then deleted it with:

```bash
gws drive files delete --params '{"fileId": "<id>"}'
```

Always clean up any throwaway test docs the same way — never leave
scratch uploads behind in the operator's Drive.
