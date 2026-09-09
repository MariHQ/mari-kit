"""Auditable whole-excerpt context packing under explicit budgets."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True, slots=True, kw_only=True)
class ContextCandidate:
    document_id: str
    revision: str
    text: str
    token_count: int
    score: float
    authorized: bool = True
    fresh: bool = True

    def __post_init__(self) -> None:
        if (
            not self.document_id.strip()
            or not self.revision.strip()
            or not self.text.strip()
        ):
            raise ValueError("context candidates require document, revision, and text")
        if self.token_count < 1:
            raise ValueError("token_count must be positive")
        if not math.isfinite(self.score):
            raise ValueError("score must be finite")


@dataclass(frozen=True, slots=True, kw_only=True)
class ContextBudget:
    tokens: int
    documents: int

    def __post_init__(self) -> None:
        if self.tokens < 0 or self.documents < 0:
            raise ValueError("context budgets must not be negative")


class ContextExclusion(StrEnum):
    UNAUTHORIZED = "unauthorized"
    STALE = "stale"
    DOCUMENT_LIMIT = "document_limit"
    TOKEN_LIMIT = "token_limit"


@dataclass(frozen=True, slots=True, kw_only=True)
class ContextTrace:
    document_id: str
    included: bool
    score: float
    reason: ContextExclusion | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ContextEnvelope:
    text: str
    document_ids: tuple[str, ...]
    revisions: tuple[tuple[str, str], ...]
    token_count: int
    trace: tuple[ContextTrace, ...]


def assemble_context(
    candidates: Iterable[ContextCandidate],
    *,
    budget: ContextBudget,
    separator: str = "\n\n",
) -> ContextEnvelope:
    """Filter before scoring output and greedily pack complete excerpts.

    Candidates are ordered by descending score and stable document identity.
    Unauthorized or stale text never enters the rendered context.
    """

    values = tuple(candidates)
    ids = [value.document_id for value in values]
    if len(ids) != len(set(ids)):
        raise ValueError("context candidate document IDs must be unique")
    ranked = sorted(values, key=lambda value: (-value.score, value.document_id))
    included: list[ContextCandidate] = []
    trace: list[ContextTrace] = []
    used = 0
    for candidate in ranked:
        reason: ContextExclusion | None = None
        if not candidate.authorized:
            reason = ContextExclusion.UNAUTHORIZED
        elif not candidate.fresh:
            reason = ContextExclusion.STALE
        elif len(included) >= budget.documents:
            reason = ContextExclusion.DOCUMENT_LIMIT
        elif used + candidate.token_count > budget.tokens:
            reason = ContextExclusion.TOKEN_LIMIT
        if reason is None:
            included.append(candidate)
            used += candidate.token_count
        trace.append(
            ContextTrace(
                document_id=candidate.document_id,
                included=reason is None,
                score=candidate.score,
                reason=reason,
            )
        )
    return ContextEnvelope(
        text=separator.join(candidate.text for candidate in included),
        document_ids=tuple(candidate.document_id for candidate in included),
        revisions=tuple(
            (candidate.document_id, candidate.revision) for candidate in included
        ),
        token_count=used,
        trace=tuple(trace),
    )
