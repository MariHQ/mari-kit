"""Framework-neutral context lifecycle contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from .knowledge import MemoryMutationPlan
from .retrieval import ContextEnvelope


class LifecyclePhase(StrEnum):
    AFTER_MODEL = "after_model"
    AFTER_TOOL = "after_tool"
    END_SESSION = "end_session"


class InterventionDisposition(StrEnum):
    INJECT = "inject"
    ABSTAIN = "abstain"


@dataclass(frozen=True, slots=True, kw_only=True)
class ContextRequest:
    request_id: str
    query: str
    purpose: str
    scopes: tuple[str, ...]
    token_budget: int

    def __post_init__(self) -> None:
        if not self.request_id.strip() or not self.query.strip() or not self.purpose.strip():
            raise ValueError("request ID, query, and purpose are required")
        if self.token_budget < 0:
            raise ValueError("token budget must not be negative")
        scopes = tuple(dict.fromkeys(scope.strip() for scope in self.scopes if scope.strip()))
        if not scopes:
            raise ValueError("at least one scope is required")
        object.__setattr__(self, "scopes", scopes)


@dataclass(frozen=True, slots=True, kw_only=True)
class LifecycleEvent:
    phase: LifecyclePhase
    request_id: str
    content: str
    source_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise ValueError("request ID is required")
        object.__setattr__(self, "source_ids", tuple(dict.fromkeys(self.source_ids)))


@dataclass(frozen=True, slots=True, kw_only=True)
class ContextIntervention:
    disposition: InterventionDisposition
    envelope: ContextEnvelope | None = None
    reason: str = ""
    predicted_utility: float | None = None

    def __post_init__(self) -> None:
        if self.disposition is InterventionDisposition.INJECT and self.envelope is None:
            raise ValueError("inject decisions require a context envelope")
        if self.disposition is InterventionDisposition.ABSTAIN and self.envelope is not None:
            raise ValueError("abstain decisions must not carry context")

    @property
    def text(self) -> str:
        return self.envelope.text if self.envelope is not None else ""


def select_intervention(
    envelope: ContextEnvelope, *, predicted_utility: float, minimum_utility: float = 0.0
) -> ContextIntervention:
    """Make a visible inject/abstain decision after retrieval and packing."""

    if predicted_utility < minimum_utility or not envelope.text:
        return ContextIntervention(
            disposition=InterventionDisposition.ABSTAIN,
            reason="below_utility_threshold" if envelope.text else "empty_context",
            predicted_utility=predicted_utility,
        )
    return ContextIntervention(
        disposition=InterventionDisposition.INJECT,
        envelope=envelope,
        reason="utility_threshold_met",
        predicted_utility=predicted_utility,
    )


class ContextProvider(Protocol):
    """Adapter seam around a framework-owned model or tool loop."""

    async def before_model(self, request: ContextRequest) -> ContextIntervention: ...

    async def after_model(self, event: LifecycleEvent) -> MemoryMutationPlan: ...

    async def after_tool(self, event: LifecycleEvent) -> MemoryMutationPlan: ...

    async def end_session(self, event: LifecycleEvent) -> MemoryMutationPlan: ...
