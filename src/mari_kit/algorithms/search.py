"""Bounded DRIFT action search and LightRAG-inspired extraction refinement.

Callbacks own model prompts, retrieval, credentials, and persistence. These are
synchronous orchestration algorithms; callback exceptions propagate unchanged.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass
from typing import Generic, Literal, TypeVar

T = TypeVar("T")
R = TypeVar("R")


@dataclass(frozen=True)
class DriftQuery:
    query: str
    score: float | None = None

    def __post_init__(self) -> None:
        if (
            not self.query.strip()
            or self.score is not None
            and not math.isfinite(self.score)
        ):
            raise ValueError("nonempty query and finite score required")


@dataclass(frozen=True)
class DriftResponse(Generic[T]):
    answer: T
    followups: tuple[DriftQuery, ...] = ()


@dataclass(frozen=True)
class DriftAction(Generic[T]):
    query: DriftQuery
    depth: int
    parent: int | None
    response: DriftResponse[T] | None = None


@dataclass(frozen=True)
class DriftResult(Generic[T, R]):
    answer: R
    actions: tuple[DriftAction[T], ...]
    completed: tuple[int, ...]
    pending: tuple[int, ...]
    stopped: Literal["exhausted", "budget"]


def drift_search(
    query: str,
    *,
    primer: Callable[[str], Sequence[DriftQuery]],
    local_search: Callable[[DriftQuery, int], DriftResponse[T]],
    reduce: Callable[[str, tuple[DriftAction[T], ...]], R],
    max_actions: int = 20,
    max_depth: int = 3,
    ranking: Literal["score", "random"] = "score",
    seed: int = 0,
) -> DriftResult[T, R]:
    """Prime, expand ranked incomplete actions, then reduce completed evidence.

    Adaptation of GraphRAG DRIFT: exact query-string deduplication prevents cycles;
    highest score wins (missing scores last), stable insertion ties. Depth 0 is
    the primer. Budget counts local calls, excluding one primer and one reducer.
    Reducer receives completed actions in execution order, with parent IDs that
    refer to the complete returned action array. No provider-specific prompts.
    """
    if (
        not query.strip()
        or max_actions < 0
        or max_depth < 0
        or ranking not in ("score", "random")
    ):
        raise ValueError("invalid query, limits or ranking")
    rng = random.Random(seed)
    actions: list[DriftAction[T]] = []
    pending: list[int] = []
    completed: list[int] = []
    seen: set[str] = set()

    def add(proposals: Sequence[DriftQuery], depth: int, parent: int | None) -> None:
        for proposal in proposals:
            if proposal.query not in seen:
                seen.add(proposal.query)
                pending.append(len(actions))
                actions.append(DriftAction(proposal, depth, parent))

    def action_score(index: int) -> float:
        score = actions[index].query.score
        return -math.inf if score is None else score

    add(primer(query), 0, None)
    while pending and len(completed) < max_actions:
        index = (
            rng.choice(pending)
            if ranking == "random"
            else max(
                pending,
                key=action_score,
            )
        )
        pending.remove(index)
        action = actions[index]
        response = local_search(action.query, action.depth)
        actions[index] = DriftAction(
            action.query, action.depth, action.parent, response
        )
        completed.append(index)
        if action.depth < max_depth:
            add(response.followups, action.depth + 1, index)
    answer = reduce(query, tuple(actions[i] for i in completed))
    return DriftResult(
        answer,
        tuple(actions),
        tuple(completed),
        tuple(pending),
        "budget" if pending else "exhausted",
    )


@dataclass(frozen=True)
class RefinementResult(Generic[T]):
    records: tuple[T, ...]
    rounds: int
    additions: tuple[int, ...]
    stopped: Literal["budget", "stable", "callback"]


def refine_extraction(
    source: str,
    *,
    extract: Callable[[str], Sequence[T]],
    refine: Callable[[str, tuple[T, ...], int], Sequence[T]],
    key: Callable[[T], Hashable],
    merge: Callable[[T, T], T],
    max_rounds: int = 1,
    should_continue: Callable[[tuple[T, ...], int], bool] | None = None,
) -> RefinementResult[T]:
    """Extract then glean additions/revisions, merging by caller identity.

    LightRAG-inspired generalization to an explicit round budget. Stable equality
    ends refinement early. ``merge`` must preserve identity. Each refinement sees
    the fully merged snapshot; inputs/outputs must be immutable caller values.
    """
    if max_rounds < 0:
        raise ValueError("max_rounds must be nonnegative")
    records: dict[Hashable, T] = {}

    def absorb(values: Sequence[T]) -> int:
        additions = 0
        for value in values:
            identity = key(value)
            if identity in records:
                value = merge(records[identity], value)
                if key(value) != identity:
                    raise ValueError("merge changed record identity")
            else:
                additions += 1
            records[identity] = value
        return additions

    absorb(extract(source))
    counts = []
    stopped: Literal["budget", "stable", "callback"] = "budget"
    for round_number in range(1, max_rounds + 1):
        before = tuple(records.values())
        if should_continue is not None and not should_continue(before, round_number):
            stopped = "callback"
            break
        counts.append(absorb(refine(source, before, round_number)))
        if tuple(records.values()) == before:
            stopped = "stable"
            break
    return RefinementResult(
        tuple(records.values()), len(counts), tuple(counts), stopped
    )
