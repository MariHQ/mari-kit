"""Extract a clean prose preview from Markdown or HTML knowledge content."""

from __future__ import annotations

import re

LIMIT = 200

_FRONT_MATTER = re.compile(r"^\s*---\s+.*?\s---\s+", re.S)
_HTML = re.compile(r"<[^>]+>")
_FENCE = re.compile(r"```[a-zA-Z0-9_-]*")
_CODE = re.compile(r"`([^`]*)`")
_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_STRONG = re.compile(r"(\*\*|__)(.*?)\1", re.S)
_EM = re.compile(r"(^|\s)(\*|_)(\S[^*_]*?)\2(?=\s|$|[.,;:!?])")
_HEADING = re.compile(r"(^|\s)#{1,6}\s+")
_QUOTE = re.compile(r"(^|\s)>\s?")
_LIST = re.compile(r"(^|\s)(?:[-*+]|\d+[.)])\s+")
_RULE = re.compile(r"(^|\s)(?:-{3,}|\*{3,}|_{3,})(?=\s|$)")
_META_RUN = re.compile(
    r"\b(?:commit\s+[0-9a-f]{7,40}|(?:PR|MR|issue|Issue)\s+#\d+)"
    r"(?:\s*·\s*[^·]*?)*?\s*·\s*(?:updated\s+)?\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?\s*"
)
_LEAD_PUNCT = re.compile(r"^[\s:.\-–—·]+")
_WS = re.compile(r"\s+")


def _strip_markdown(s: str) -> str:
    s = _HTML.sub(" ", s)
    s = _FENCE.sub(" ", s)
    s = _CODE.sub(r"\1", s)
    s = _IMAGE.sub(" ", s)
    s = _LINK.sub(r"\1", s)
    s = _STRONG.sub(r"\2", s)
    s = _EM.sub(r"\1\3", s)
    s = _HEADING.sub(r"\1", s)
    s = _QUOTE.sub(r"\1", s)
    s = _LIST.sub(r"\1", s)
    s = _RULE.sub(r"\1", s)
    return _WS.sub(" ", s).strip()


def _drop_leading_title(s: str, title: str) -> str:
    t = title.strip().lower()
    if not t:
        return s
    for _ in range(3):
        if not s.lower().startswith(t):
            break
        s = _LEAD_PUNCT.sub("", s[len(t):])
    return s


def excerpt(body: str | None, title: str | None = None, limit: int = LIMIT) -> str:
    """The first `limit` characters of the body's prose, or "" for no body."""
    if not body:
        return ""
    # Only the head of the body matters, but the preamble can be long (a big
    # front-matter block, a badge table), so look further than we return.
    head = body[: max(limit * 12, 2400)].replace("\r\n", "\n").replace("\r", "\n")
    s = _FRONT_MATTER.sub("", head)
    s = _strip_markdown(s.replace("\n", " "))
    if title:
        s = _drop_leading_title(s, title)
        s = _META_RUN.sub("", s)
        s = _drop_leading_title(s, title)
    else:
        s = _META_RUN.sub("", s)
    s = _WS.sub(" ", s).strip()
    if not s:
        s = _strip_markdown(head.replace("\n", " "))
    if len(s) <= limit:
        return s
    # Cut on a word, not mid-word; the card adds its own ellipsis.
    cut = s[:limit]
    sp = cut.rfind(" ")
    return (cut[:sp] if sp > limit // 2 else cut).rstrip(" ,;:-–—·")
