"""Small, storage-independent validation helpers for knowledge products."""

from __future__ import annotations

import datetime as dt
import re


TONES = frozenset({"ink", "ok", "attention", "blocked", "info"})
SEVERITIES = frozenset({"error", "warn", "advisory"})
TEMPLATE_ICONS = frozenset({
    "clipboard", "git-fork", "shield-check", "file-text",
    "sprout", "book-open", "megaphone",
})

_METADATA_CLAIM = re.compile(
    r"""(^\s*(PR|MR|Issue|Commit)\s*\#?\d)
      | (\d{4}-\d{2}-\d{2}T\d{2}:\d{2})
      | (^[^.!?]*·[^.!?]*·)
    """,
    re.IGNORECASE | re.VERBOSE,
)


def is_claim(text: str) -> bool:
    """Return whether text looks like a checkable prose claim, not metadata."""
    claim = (text or "").strip()
    return bool(claim) and len(claim.split()) >= 4 and not _METADATA_CLAIM.search(claim)


def iso_date(value: str | None) -> str | None:
    """Normalize an ISO date or timestamp to YYYY-MM-DD."""
    if value is None or not str(value).strip():
        return None
    text = str(value).strip()
    try:
        return dt.date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        raise ValueError(
            f"Due date must be an ISO date (YYYY-MM-DD), got {text!r}"
        ) from None


def slug(value: str, maximum: int = 64) -> str:
    """Return a stable lowercase URL-safe key."""
    return re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")[:maximum]
