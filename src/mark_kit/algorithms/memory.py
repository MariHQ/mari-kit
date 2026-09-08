"""Selectable MemoryOS, A-MEM and ACE-inspired pure memory policies."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Literal


def memory_heat(
    visits: int,
    interactions: int,
    age_hours: float,
    *,
    alpha: float = 1,
    beta: float = 1,
    gamma: float = 1,
    tau_hours: float = 24,
) -> float:
    """MemoryOS raw heat: alpha*visits + beta*interactions + gamma*exp(-age/tau)."""
    if (
        visits < 0
        or interactions < 0
        or any(not math.isfinite(v) or v < 0 for v in (age_hours, alpha, beta, gamma))
        or not math.isfinite(tau_hours)
        or tau_hours <= 0
    ):
        raise ValueError("nonnegative counts/weights/age and positive tau required")
    return (
        alpha * visits + beta * interactions + gamma * math.exp(-age_hours / tau_hours)
    )


def lfu_evictions(
    frequencies: Mapping[str, int],
    *,
    capacity: int,
    protected: frozenset[str] = frozenset(),
) -> tuple[str, ...]:
    """Evict least frequent first, insertion-order ties; fail if protection prevents capacity."""
    if capacity < 0 or any(v < 0 for v in frequencies.values()):
        raise ValueError("capacity/frequencies must be nonnegative")
    needed = max(0, len(frequencies) - capacity)
    available = [key for key in frequencies if key not in protected]
    if len(available) < needed:
        raise ValueError("protected entries prevent requested capacity")
    return tuple(sorted(available, key=lambda key: frequencies[key])[:needed])


def heat_promotions(
    heats: Mapping[str, float], *, threshold: float, limit: int | None = None
) -> tuple[str, ...]:
    """Choose strictly above-threshold heat, hottest first, stable insertion ties."""
    if (
        not math.isfinite(threshold)
        or any(not math.isfinite(v) for v in heats.values())
        or limit is not None
        and limit < 0
    ):
        raise ValueError("finite heats/threshold and nonnegative limit required")
    return tuple(
        sorted(
            (key for key, value in heats.items() if value > threshold),
            key=lambda key: -heats[key],
        )[:limit]
    )


@dataclass(frozen=True)
class MemoryNote:
    id: str
    revision: int
    context: str
    tags: tuple[str, ...] = ()
    links: tuple[str, ...] = ()


@dataclass(frozen=True)
class NoteUpdate:
    id: str
    expected_revision: int
    context: str | None = None
    tags: tuple[str, ...] | None = None
    add_links: tuple[str, ...] = ()


@dataclass(frozen=True)
class NoteChange:
    before: MemoryNote
    after: MemoryNote


def evolve_neighborhood(
    focus: MemoryNote,
    neighbors: Sequence[MemoryNote],
    *,
    propose: Callable[[MemoryNote, tuple[MemoryNote, ...]], Sequence[NoteUpdate]],
) -> tuple[NoteChange, ...]:
    """A-MEM-inspired callback evolution with explicit IDs and revision guards.

    Proposal can strengthen links and update focus/neighbor context or tags.
    Returns changes for a host to compare-and-swap atomically; writes nothing.
    Only supplied neighborhood IDs may be updated or linked. Duplicate proposals,
    self links, unknown targets and stale revisions fail the entire plan.
    """
    notes = (focus, *neighbors)
    current = {note.id: note for note in notes}
    if len(current) != len(notes) or any(
        not note.id or note.revision < 0 for note in notes
    ):
        raise ValueError("unique note IDs and nonnegative revisions required")
    changes = []
    seen = set()
    for update in propose(focus, tuple(neighbors)):
        if update.id in seen or update.id not in current:
            raise ValueError("duplicate or unknown update target")
        seen.add(update.id)
        before = current[update.id]
        if before.revision != update.expected_revision:
            raise ValueError("stale revision")
        if any(link not in current or link == update.id for link in update.add_links):
            raise ValueError("link outside neighborhood or self link")
        after = replace(
            before,
            context=before.context if update.context is None else update.context,
            tags=before.tags
            if update.tags is None
            else tuple(dict.fromkeys(update.tags)),
            links=tuple(dict.fromkeys((*before.links, *update.add_links))),
        )
        if after != before:
            changes.append(
                NoteChange(before, replace(after, revision=before.revision + 1))
            )
    return tuple(changes)


@dataclass(frozen=True)
class SkillRecord:
    id: str
    text: str
    helpful: int = 0
    harmful: int = 0
    neutral: int = 0
    provenance: tuple[str, ...] = ()
    deleted: bool = False

    def __post_init__(self) -> None:
        if not self.id or min(self.helpful, self.harmful, self.neutral) < 0:
            raise ValueError("ID and nonnegative counters required")


@dataclass(frozen=True)
class SkillFeedback:
    event_id: str
    skill_id: str
    label: Literal["helpful", "harmful", "neutral"]
    source: str


@dataclass(frozen=True)
class SkillDecision:
    action: Literal["keep", "update", "delete", "merge"]
    target: str
    sources: tuple[str, ...] = ()
    text: str | None = None


@dataclass(frozen=True)
class SkillReduction:
    records: tuple[SkillRecord, ...]
    applied_events: frozenset[str]


def reduce_skill_feedback(
    records: Sequence[SkillRecord],
    feedback: Sequence[SkillFeedback],
    *,
    decisions: Sequence[SkillDecision] = (),
    applied_events: frozenset[str] = frozenset(),
) -> SkillReduction:
    """ACE-inspired feedback and explicit dedup decisions over immutable snapshots.

    Feedback IDs make replay idempotent when the host persists applied_events.
    Merge adds counters/provenance to its retained target and tombstones sources.
    Decisions run in supplied order, cannot act on deleted records, and should be
    committed once with the returned snapshot (decision replay is not idempotent).
    """
    state = {record.id: record for record in records}
    if len(state) != len(records):
        raise ValueError("duplicate skill IDs")
    events = set(applied_events)
    for event in feedback:
        if not event.event_id or event.label not in ("helpful", "harmful", "neutral"):
            raise ValueError("invalid feedback event")
        if event.event_id in events:
            continue
        record = state[event.skill_id]
        if record.deleted:
            raise ValueError("feedback targets deleted skill")
        counters = (
            record.helpful + (event.label == "helpful"),
            record.harmful + (event.label == "harmful"),
            record.neutral + (event.label == "neutral"),
        )
        state[record.id] = replace(
            record,
            helpful=counters[0],
            harmful=counters[1],
            neutral=counters[2],
            provenance=tuple(dict.fromkeys((*record.provenance, event.source))),
        )
        events.add(event.event_id)
    for decision in decisions:
        target = state[decision.target]
        if target.deleted:
            raise ValueError("decision targets deleted skill")
        if decision.action == "merge":
            if (
                not decision.sources
                or len(set(decision.sources)) != len(decision.sources)
                or target.id in decision.sources
            ):
                raise ValueError("merge needs distinct non-target sources")
            sources = [state[key] for key in decision.sources]
            if any(source.deleted for source in sources):
                raise ValueError("cannot merge deleted source")
            target = replace(
                target,
                helpful=target.helpful + sum(s.helpful for s in sources),
                harmful=target.harmful + sum(s.harmful for s in sources),
                neutral=target.neutral + sum(s.neutral for s in sources),
                provenance=tuple(
                    dict.fromkeys(
                        (
                            *target.provenance,
                            *(p for s in sources for p in s.provenance),
                        )
                    )
                ),
            )
            for source in sources:
                state[source.id] = replace(source, deleted=True)
        elif decision.sources:
            raise ValueError("only merge accepts sources")
        elif decision.action == "delete":
            target = replace(target, deleted=True)
        elif decision.action == "update":
            if decision.text is None:
                raise ValueError("update requires text")
        elif decision.action != "keep":
            raise ValueError("unknown decision")
        if decision.text is not None:
            if decision.action not in ("update", "merge"):
                raise ValueError("only update/merge accept text")
            target = replace(target, text=decision.text)
        state[target.id] = target
    return SkillReduction(tuple(state.values()), frozenset(events))
