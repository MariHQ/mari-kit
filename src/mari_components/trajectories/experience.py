"""Contrastive trajectory associations and evidence-bound reasoning memories."""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from mari_components.errors import MalformedModelOutput
from mari_components.json import require_list

from .intents import IntentEvidence
from .process import TrajectoryRun, canonicalize_activity

REASONING_MEMORY_VERSION = "reasoning-memory-v1"


@dataclass(frozen=True, slots=True, kw_only=True)
class OutcomeAssociation:
    pattern: tuple[str, ...]
    success_support: int
    failure_support: int
    success_total: int
    failure_total: int
    failure_risk_ratio: float
    risk_ratio_interval: tuple[float, float]
    successful_trajectory_ids: tuple[str, ...]
    failing_trajectory_ids: tuple[str, ...]

    @property
    def support(self) -> int:
        return self.success_support + self.failure_support


def mine_outcome_associations(
    runs: Iterable[TrajectoryRun],
    *,
    minimum_support: int = 2,
    maximum_pattern_length: int = 4,
    confidence: float = 0.95,
) -> tuple[OutcomeAssociation, ...]:
    """Find contiguous activity patterns associated with observed run outcomes.

    Risk ratios compare pattern prevalence in failed runs with prevalence in
    successful runs. They are descriptive associations, not causal effects.
    """

    if minimum_support < 1 or maximum_pattern_length < 1:
        raise ValueError("support and pattern length must be positive")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be in (0, 1)")
    values = tuple(run for run in runs if run.outcome in {"success", "failure"})
    if len({run.trajectory_id for run in values}) != len(values):
        raise ValueError("trajectory IDs must be unique")
    successes = tuple(run for run in values if run.outcome == "success")
    failures = tuple(run for run in values if run.outcome == "failure")
    if not successes or not failures:
        return ()
    patterns: dict[tuple[str, ...], dict[str, set[str]]] = {}
    for run in values:
        activities = tuple(canonicalize_activity(step.tool) for step in run.steps)
        observed = {
            activities[start : start + size]
            for size in range(1, min(maximum_pattern_length, len(activities)) + 1)
            for start in range(len(activities) - size + 1)
        }
        for pattern in observed:
            buckets = patterns.setdefault(pattern, {"success": set(), "failure": set()})
            buckets[run.outcome].add(run.trajectory_id)
    z = _normal_quantile(0.5 + confidence / 2)
    output: list[OutcomeAssociation] = []
    for pattern, buckets in patterns.items():
        success_ids = tuple(sorted(buckets["success"]))
        failure_ids = tuple(sorted(buckets["failure"]))
        if len(success_ids) + len(failure_ids) < minimum_support:
            continue
        ratio, interval = _risk_ratio(
            len(failure_ids), len(failures), len(success_ids), len(successes), z
        )
        output.append(
            OutcomeAssociation(
                pattern=pattern,
                success_support=len(success_ids),
                failure_support=len(failure_ids),
                success_total=len(successes),
                failure_total=len(failures),
                failure_risk_ratio=ratio,
                risk_ratio_interval=interval,
                successful_trajectory_ids=success_ids,
                failing_trajectory_ids=failure_ids,
            )
        )
    return tuple(
        sorted(
            output,
            key=lambda item: (
                -abs(math.log(item.failure_risk_ratio)),
                -item.support,
                item.pattern,
            ),
        )
    )


class ReasoningMemoryKind(StrEnum):
    STRATEGY = "strategy"
    PITFALL = "pitfall"
    HEURISTIC = "heuristic"


@dataclass(frozen=True, slots=True, kw_only=True)
class ReasoningMemoryCandidate:
    memory_id: str
    title: str
    description: str
    content: str
    kind: ReasoningMemoryKind
    evidence: tuple[IntentEvidence, ...]
    applicability: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    schema_version: str = REASONING_MEMORY_VERSION


@dataclass(frozen=True, slots=True, kw_only=True)
class ReasoningMemoryComparison:
    added: tuple[str, ...]
    removed: tuple[str, ...]
    unchanged: tuple[str, ...]
    revised: tuple[tuple[str, str], ...]


def parse_reasoning_memories(
    runs: Iterable[TrajectoryRun], model_output: object
) -> tuple[ReasoningMemoryCandidate, ...]:
    """Validate proposed reusable insights against exact trajectory ranges."""

    known = {run.trajectory_id: run for run in runs}
    rows = require_list(model_output, "memories", recipe=REASONING_MEMORY_VERSION)
    output: list[ReasoningMemoryCandidate] = []
    for row in rows:
        title = str(row.get("title") or "").strip()[:160]
        description = str(row.get("description") or "").strip()[:500]
        content = str(row.get("content") or "").strip()[:2_000]
        if not title or not description or not content:
            raise MalformedModelOutput("reasoning memory text fields are required")
        try:
            kind = ReasoningMemoryKind(str(row.get("kind") or "heuristic"))
        except ValueError as error:
            raise MalformedModelOutput("reasoning memory kind is invalid") from error
        raw_evidence = row.get("evidence")
        if not isinstance(raw_evidence, list) or not raw_evidence:
            raise MalformedModelOutput("reasoning memory evidence is required")
        evidence: list[IntentEvidence] = []
        for item in raw_evidence:
            if not isinstance(item, dict):
                raise MalformedModelOutput("reasoning memory evidence must be objects")
            trajectory_id = str(item.get("trajectory_id") or "")
            run = known.get(trajectory_id)
            if run is None:
                raise MalformedModelOutput("reasoning memory references an unknown run")
            start, end = _bounds(item)
            if start < 0 or end < start or end >= len(run.steps):
                raise MalformedModelOutput(
                    "reasoning memory evidence is outside the run"
                )
            evidence.append(
                IntentEvidence(trajectory_id=trajectory_id, start=start, end=end)
            )
        evidence_values = tuple(
            sorted(
                set(evidence),
                key=lambda item: (item.trajectory_id, item.start, item.end),
            )
        )
        identity = "\0".join(
            (
                kind.value,
                _key(title),
                *(f"{e.trajectory_id}:{e.start}:{e.end}" for e in evidence_values),
            )
        )
        output.append(
            ReasoningMemoryCandidate(
                memory_id=f"reasoning:{hashlib.sha256(identity.encode()).hexdigest()[:20]}",
                title=title,
                description=description,
                content=content,
                kind=kind,
                evidence=evidence_values,
                applicability=_strings(row.get("applicability"), "applicability"),
                limitations=_strings(row.get("limitations"), "limitations"),
            )
        )
    by_id = {item.memory_id: item for item in output}
    return tuple(by_id[key] for key in sorted(by_id))


def compare_reasoning_memories(
    existing: Iterable[ReasoningMemoryCandidate],
    proposed: Iterable[ReasoningMemoryCandidate],
) -> ReasoningMemoryComparison:
    """Compare memory sets by identity and normalized title without applying changes."""

    left = tuple(existing)
    right = tuple(proposed)
    left_ids, right_ids = (
        {item.memory_id for item in left},
        {item.memory_id for item in right},
    )
    left_titles = {_key(item.title): item for item in left}
    right_titles = {_key(item.title): item for item in right}
    revised = tuple(
        sorted(
            (left_titles[key].memory_id, right_titles[key].memory_id)
            for key in left_titles.keys() & right_titles.keys()
            if left_titles[key].memory_id != right_titles[key].memory_id
        )
    )
    revised_left = {left_id for left_id, _ in revised}
    revised_right = {right_id for _, right_id in revised}
    return ReasoningMemoryComparison(
        added=tuple(sorted(right_ids - left_ids - revised_right)),
        removed=tuple(sorted(left_ids - right_ids - revised_left)),
        unchanged=tuple(sorted(left_ids & right_ids)),
        revised=revised,
    )


def _risk_ratio(
    a: int, n1: int, c: int, n0: int, z: float
) -> tuple[float, tuple[float, float]]:
    # Haldane-Anscombe correction keeps zero-cell estimates finite and visible.
    aa, cc, nn1, nn0 = a + 0.5, c + 0.5, n1 + 1.0, n0 + 1.0
    ratio = (aa / nn1) / (cc / nn0)
    standard_error = math.sqrt(1 / aa - 1 / nn1 + 1 / cc - 1 / nn0)
    center = math.log(ratio)
    return ratio, (
        math.exp(center - z * standard_error),
        math.exp(center + z * standard_error),
    )


def _normal_quantile(probability: float) -> float:
    # Acklam's rational approximation, accurate enough for confidence reporting.
    a = (
        -39.6968302866538,
        220.946098424521,
        -275.928510446969,
        138.357751867269,
        -30.6647980661472,
        2.50662827745924,
    )
    b = (
        -54.4760987982241,
        161.585836858041,
        -155.698979859887,
        66.8013118877197,
        -13.2806815528857,
    )
    c = (
        -0.00778489400243029,
        -0.322396458041136,
        -2.40075827716184,
        -2.54973253934373,
        4.37466414146497,
        2.93816398269878,
    )
    d = (0.00778469570904146, 0.32246712907004, 2.445134137143, 3.75440866190742)
    low, high = 0.02425, 0.97575
    if probability < low:
        q = math.sqrt(-2 * math.log(probability))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
        )
    if probability > high:
        q = math.sqrt(-2 * math.log(1 - probability))
        return -(
            ((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]
        ) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    q = probability - 0.5
    r = q * q
    return (
        (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5])
        * q
        / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
    )


def _bounds(item: Mapping[str, object]) -> tuple[int, int]:
    if isinstance(item.get("start"), bool) or isinstance(item.get("end"), bool):
        raise MalformedModelOutput("reasoning memory bounds must be integers")
    raw_start, raw_end = item.get("start"), item.get("end")
    if not isinstance(raw_start, (str, int, float)) or not isinstance(
        raw_end, (str, int, float)
    ):
        raise MalformedModelOutput("reasoning memory bounds must be integers")
    try:
        return int(raw_start), int(raw_end)
    except (TypeError, ValueError) as error:
        raise MalformedModelOutput(
            "reasoning memory bounds must be integers"
        ) from error


def _strings(value: object, name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise MalformedModelOutput(f"reasoning memory {name} must be strings")
    return tuple(item.strip()[:300] for item in value if item.strip())


def _key(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())
