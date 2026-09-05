"""Inspect citation declarations against explicit evidence event ordering.

Adapted from haiku.rag's evidence ledger; see THIRD_PARTY_NOTICES.md.
A current declaration records attribution, not semantic entailment.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from mari_components.references import RevisionRef


@dataclass(frozen=True, slots=True, kw_only=True)
class OwnedEvidenceRef:
    owner: str
    ref: RevisionRef

    def __post_init__(self) -> None:
        if not self.owner.strip():
            raise ValueError("evidence owner is required")


class CitationEventKind(StrEnum):
    OUTCOME = "outcome"
    DECLARATION = "declaration"


@dataclass(frozen=True, slots=True, kw_only=True)
class CitationEvent:
    """An outcome may contain zero refs (for example, an empty search).

    Ordinals are host-supplied ordering within an activity, shared by all owners.
    Simultaneous events may share an ordinal; a declaration must be strictly
    later than an outcome to acknowledge it. Failures without evidence should
    not be recorded as outcomes.
    """

    event_id: str
    activity_id: str
    owner: str
    ordinal: int
    kind: CitationEventKind
    refs: tuple[OwnedEvidenceRef, ...] = ()

    def __post_init__(self) -> None:
        if not all(
            (self.event_id.strip(), self.activity_id.strip(), self.owner.strip())
        ):
            raise ValueError("citation events require event, activity, and owner IDs")
        if self.ordinal < 0 or not isinstance(self.kind, CitationEventKind):
            raise ValueError("citation event ordinal or kind is invalid")
        object.__setattr__(self, "refs", tuple(dict.fromkeys(self.refs)))
        if self.kind is CitationEventKind.OUTCOME and any(
            ref.owner != self.owner for ref in self.refs
        ):
            raise ValueError("outcomes may only publish their owner's evidence")


class CitationDeclarationStatus(StrEnum):
    MISSING = "missing"
    STALE = "stale"
    DECLARED = "declared"
    EMPTY = "empty"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True, kw_only=True)
class CitationDeclarationReport:
    activity_id: str
    status: CitationDeclarationStatus
    refs: tuple[OwnedEvidenceRef, ...]
    unknown_refs: tuple[OwnedEvidenceRef, ...]
    latest_outcome_ordinal: int | None
    declaration_event_ids: tuple[str, ...]


def inspect_citation_declarations(
    events: Iterable[CitationEvent],
    *,
    activity_id: str,
    available_evidence: Iterable[OwnedEvidenceRef] = (),
) -> CitationDeclarationReport:
    """Combine current declarations across owners without retrying an agent.

    ``available_evidence`` contains evidence already shown before this activity.
    Within this activity a ref must have been published strictly before the
    declaration. New outcomes invalidate older declarations across every owner.
    Repeated declarations after the same outcome union their refs, so an empty
    declaration cannot erase an earlier nonempty one.
    """
    if not activity_id.strip():
        raise ValueError("activity ID is required")
    values = tuple(events)
    if len({event.event_id for event in values}) != len(values):
        raise ValueError("citation event IDs must be unique")
    current = sorted(
        (event for event in values if event.activity_id == activity_id),
        key=lambda event: (event.ordinal, event.event_id),
    )
    outcomes = [e for e in current if e.kind is CitationEventKind.OUTCOME]
    declarations = [e for e in current if e.kind is CitationEventKind.DECLARATION]
    horizon = max((event.ordinal for event in outcomes), default=-1)
    standing = [event for event in declarations if event.ordinal > horizon]
    refs: dict[OwnedEvidenceRef, None] = {}
    unknown: dict[OwnedEvidenceRef, None] = {}
    carried = set(available_evidence)
    for event in standing:
        known = carried | {
            ref
            for outcome in outcomes
            if outcome.ordinal < event.ordinal
            for ref in outcome.refs
        }
        for ref in event.refs:
            refs[ref] = None
            if ref not in known:
                unknown[ref] = None
    status = (
        CitationDeclarationStatus.INVALID
        if unknown
        else CitationDeclarationStatus.DECLARED
        if refs
        else CitationDeclarationStatus.EMPTY
        if standing
        else CitationDeclarationStatus.STALE
        if declarations
        else CitationDeclarationStatus.MISSING
    )
    return CitationDeclarationReport(
        activity_id=activity_id,
        status=status,
        refs=tuple(refs),
        unknown_refs=tuple(unknown),
        latest_outcome_ordinal=horizon if horizon >= 0 else None,
        declaration_event_ids=tuple(event.event_id for event in standing),
    )
