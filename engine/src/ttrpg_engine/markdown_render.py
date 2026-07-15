"""Shared markdown -> sanitized HTML rendering.

Used by the printable-docs export (export.py) and the live viewer's story
feed (story.py). Authored markdown may embed raw HTML, so rendered output
is passed through a defense-in-depth sanitizer before it reaches a page.
"""
import html as html_lib
import re

import markdown as md_lib

_MD_EXTENSIONS = ["tables", "fenced_code", "sane_lists"]

esc = html_lib.escape

# python-markdown passes raw HTML embedded in the source straight through
# unchanged, so authored markdown (setting.md, history.md, adventure.md,
# quest-board.md) can smuggle live script-capable markup into an export.
# These patterns strip the concrete risky shapes: <script>/<style> blocks
# (including their content), bare <iframe>/<object>/<embed>/<link> tags,
# inline event-handler attributes (onclick=, onerror=, ...), and
# javascript: URLs in href/src.
_MD_TAG_WITH_CONTENT_RE = re.compile(
    r"<(script|style)\b[^>]*>.*?</\1\s*>", re.IGNORECASE | re.DOTALL
)
_MD_DANGEROUS_TAG_RE = re.compile(
    r"</?(?:script|iframe|object|embed|link|style)\b[^>]*>", re.IGNORECASE
)
_MD_EVENT_ATTR_RE = re.compile(
    r"""\s+on\w+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)""", re.IGNORECASE
)
_MD_JS_URL_ATTR_RE = re.compile(
    r"""\s+(?:href|src)\s*=\s*(?:"\s*javascript:[^"]*"|'\s*javascript:[^']*')""",
    re.IGNORECASE,
)


def sanitize_html(rendered: str) -> str:
    """Strip script-capable HTML from already-rendered markdown output.

    This is a compact regex pass, not a full HTML sanitizer — it is
    defense-in-depth for a local, single-operator tool, not a security
    boundary for adversarial input. It does not parse HTML, so it can be
    defeated by deliberately obfuscated markup (odd whitespace/encoding,
    tags split across entities, unclosed/malformed tags, etc.). It targets
    the concrete threats worth covering here (script/style/iframe/object/
    embed/link elements, inline event handlers, javascript: URLs) and
    leaves ordinary markdown output (headings, tables, emphasis, em-dashes,
    ...) untouched.
    """
    rendered = _MD_TAG_WITH_CONTENT_RE.sub("", rendered)
    rendered = _MD_DANGEROUS_TAG_RE.sub("", rendered)
    rendered = _MD_EVENT_ATTR_RE.sub("", rendered)
    rendered = _MD_JS_URL_ATTR_RE.sub("", rendered)
    return rendered


def render_markdown(text: str) -> str:
    """Render markdown to sanitized, self-contained HTML."""
    rendered = md_lib.markdown((text or "").strip(), extensions=_MD_EXTENSIONS)
    return sanitize_html(rendered)
