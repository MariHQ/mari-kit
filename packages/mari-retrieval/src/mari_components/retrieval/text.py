"""Deterministic text preparation for derived retrieval indexes."""

from __future__ import annotations

import hashlib


def chunk_text(text: str, max_tokens: int, overlap: int) -> list[str]:
    """Split text with a dependency-free word approximation of token counts."""
    words = text.split()
    size = max(int(max_tokens * 0.75), 32)
    step = max(size - int(overlap * 0.75), size // 2)
    if len(words) <= size:
        return [" ".join(words)] if words else []
    return [" ".join(words[index:index + size]) for index in range(0, len(words), step)
            if words[index:index + size]]


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def title_from_markdown(text: str, fallback: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("# ").strip() or fallback
    return fallback
