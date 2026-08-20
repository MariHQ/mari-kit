"""Deterministic scores derived from validated evidence, never model opinion."""

from __future__ import annotations

import re
from collections.abc import Iterable

from mari_components.types import Evidence


_TOKEN = re.compile(r"[\w]+", re.UNICODE)


def evidence_confidence(text: str, evidence: Iterable[Evidence]) -> float:
    """Return a reproducible grounding score in ``[0, 1]``.

    Eighty percent measures how much of the candidate text occurs in its exact,
    already-validated evidence quotes. Ten percent rewards independent source
    documents and ten percent rewards multiple citations. Source and citation
    credit saturate at two, so volume cannot manufacture confidence.

    This is evidence coverage, not a model probability or a truth probability.
    A single exact citation scores ``0.9``; corroboration from a second document
    can raise it to ``1.0``.
    """
    citations = tuple(evidence)
    target = set(_TOKEN.findall(text.casefold()))
    if not target or not citations:
        return 0.0
    supported = set(_TOKEN.findall(" ".join(item.quote for item in citations).casefold()))
    coverage = len(target & supported) / len(target)
    source_credit = min(len({item.document_id for item in citations}), 2) / 2
    citation_credit = min(len(citations), 2) / 2
    return round(0.8 * coverage + 0.1 * source_credit + 0.1 * citation_credit, 4)
