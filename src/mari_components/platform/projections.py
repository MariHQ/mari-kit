"""Ordered event replay into disposable deterministic projections."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, TypeVar

StateT = TypeVar("StateT")


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeEvent:
    event_id: str
    generation: int
    kind: str
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_id.strip() or not self.kind.strip() or self.generation < 1:
            raise ValueError("event ID, kind, and positive generation are required")
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectionBuild:
    state: Any
    generation: int
    event_ids: tuple[str, ...]
    build_id: str


def replay_projection(
    initial: StateT,
    events: Iterable[KnowledgeEvent],
    *,
    projector: Callable[[StateT, KnowledgeEvent], StateT],
    starting_generation: int = 0,
) -> ProjectionBuild:
    """Fold a contiguous, unique event stream and fingerprint the build input."""

    values = tuple(events)
    event_ids = [event.event_id for event in values]
    if len(event_ids) != len(set(event_ids)):
        raise ValueError("event IDs must be unique")
    expected = starting_generation + 1
    state = initial
    for event in values:
        if event.generation != expected:
            raise ValueError(f"expected generation {expected}, got {event.generation}")
        state = projector(state, event)
        expected += 1
    identity = json.dumps(
        [
            {
                "id": event.event_id,
                "generation": event.generation,
                "kind": event.kind,
                "payload": dict(event.payload),
            }
            for event in values
        ],
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode()
    return ProjectionBuild(
        state=state,
        generation=expected - 1,
        event_ids=tuple(event_ids),
        build_id=f"sha256:{hashlib.sha256(identity).hexdigest()}",
    )
