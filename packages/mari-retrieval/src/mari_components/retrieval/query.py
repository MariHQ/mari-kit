"""Pure query-text helpers for keyword retrieval adapters."""

from __future__ import annotations

def keyword_score(title: str, text: str, terms: list[str]) -> float:
    if not terms:
        return 1.0
    normalized_title = title.lower()
    normalized_text = text.lower()
    hits = sum(
        2 * normalized_title.count(term) + min(3, normalized_text.count(term))
        for term in terms
    )
    return min(1.0, hits / max(1.0, len(terms) * 2.0))
