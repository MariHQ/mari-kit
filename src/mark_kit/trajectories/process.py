"""Deterministic process-mining summaries over caller-owned trajectories."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from .normalize import TrajectoryStep

_PARENS = re.compile(r"\s*\([^()]*\)")
_BRACKETS = re.compile(r"\s*\[[^\[\]]*\]")
_ATTEMPT = re.compile(r"[-_](?:attempt|try|retry|n)[-_]?\d+$", re.I)
_NUMBERED_ID = re.compile(r"[-_/]\d[\w.]*$")
_PATH_ARGUMENT = re.compile(r"[\s:=]+[~./]?[\w.-]*/[\w./-]*")
_SPACE = re.compile(r"\s+")


def canonicalize_activity(label: str) -> str:
    """Remove arguments, paths, retry suffixes, and generated IDs from a label."""

    value = str(label)
    for _ in range(3):
        reduced = _BRACKETS.sub("", _PARENS.sub("", value))
        if reduced == value:
            break
        value = reduced
    value = _ATTEMPT.sub("", value)
    value = _PATH_ARGUMENT.sub("", value)
    value = _NUMBERED_ID.sub("", value)
    value = _SPACE.sub(" ", value).strip(" :/-_")
    if ":" in value:
        prefix, _, suffix = value.partition(":")
        if prefix in {"chat", "completion", "embedding", "text_completion"}:
            return prefix
        value = f"{prefix}:{suffix}" if suffix else prefix
    return value or "unknown"


@dataclass(frozen=True, slots=True, kw_only=True)
class TrajectoryRun:
    trajectory_id: str
    steps: tuple[TrajectoryStep, ...]
    outcome: str = "unknown"

    def __post_init__(self) -> None:
        if not self.trajectory_id.strip():
            raise ValueError("trajectory ID is required")
        if self.outcome not in {"success", "failure", "unknown"}:
            raise ValueError("trajectory outcome must be success, failure, or unknown")
        object.__setattr__(self, "steps", tuple(self.steps))


@dataclass(frozen=True, slots=True, kw_only=True)
class ActivityStatistics:
    activity: str
    occurrences: int
    failures: int
    unknown_outcomes: int
    duration: float
    tokens: int
    cost: float


@dataclass(frozen=True, slots=True, kw_only=True)
class TransitionStatistics:
    source: str
    target: str
    occurrences: int
    parallel: int
    duration: float
    cost: float


@dataclass(frozen=True, slots=True, kw_only=True)
class TrajectoryVariant:
    activities: tuple[str, ...]
    trajectory_ids: tuple[str, ...]
    total_cost: float
    total_duration: float

    @property
    def occurrences(self) -> int:
        return len(self.trajectory_ids)


@dataclass(slots=True)
class _VariantAccumulator:
    ids: list[str] = field(default_factory=list)
    cost: float = 0.0
    duration: float = 0.0


@dataclass(frozen=True, slots=True, kw_only=True)
class TrajectoryProcess:
    activities: Mapping[str, ActivityStatistics]
    transitions: tuple[TransitionStatistics, ...]
    variants: tuple[TrajectoryVariant, ...]
    trajectory_count: int
    event_count: int
    rework_events: int
    parallel_events: int
    total_tokens: int
    total_cost: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "activities", MappingProxyType(dict(self.activities)))

    @property
    def rework_rate(self) -> float:
        return self.rework_events / self.event_count if self.event_count else 0.0

    @property
    def variant_reuse(self) -> float:
        if not self.trajectory_count:
            return 0.0
        repeated = sum(
            item.occurrences for item in self.variants if item.occurrences > 1
        )
        return repeated / self.trajectory_count


def mine_trajectory_process(
    runs: Iterable[TrajectoryRun],
    *,
    activity_aliases: Mapping[str, str] = MappingProxyType({}),
) -> TrajectoryProcess:
    """Build a direct-follow graph, variants, and rework statistics.

    Steps sharing a non-empty ``parent_id`` are treated as one parallel batch,
    so repeated tools in that batch do not inflate sequential rework.
    """

    values = tuple(runs)
    if len({run.trajectory_id for run in values}) != len(values):
        raise ValueError("trajectory IDs must be unique")
    node: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {
            "n": 0,
            "failures": 0,
            "unknown": 0,
            "duration": 0.0,
            "tokens": 0,
            "cost": 0.0,
        }
    )
    edges: dict[tuple[str, str], dict[str, float | int]] = defaultdict(
        lambda: {"n": 0, "parallel": 0, "duration": 0.0, "cost": 0.0}
    )
    variants: dict[tuple[str, ...], _VariantAccumulator] = {}
    event_count = rework = parallel_events = total_tokens = 0
    total_cost = 0.0

    for run in values:
        activities = tuple(
            activity_aliases.get(step.tool, canonicalize_activity(step.tool))
            for step in run.steps
        )
        parent_counts = Counter(step.parent_id for step in run.steps if step.parent_id)
        parallel_parents = {
            parent for parent, count in parent_counts.items() if count > 1
        }
        parallel_events += sum(step.parent_id in parallel_parents for step in run.steps)
        seen: Counter[str] = Counter()
        seen_batches: set[tuple[str, str]] = set()
        run_cost = run_duration = 0.0
        for index, (step, activity) in enumerate(
            zip(run.steps, activities, strict=True)
        ):
            stats = node[activity]
            stats["n"] += 1
            stats["failures"] += int(step.ok is False)
            stats["unknown"] += int(step.ok is None)
            stats["duration"] += step.duration
            stats["tokens"] += step.tokens
            stats["cost"] += step.cost
            event_count += 1
            total_tokens += step.tokens
            total_cost += step.cost
            run_cost += step.cost
            run_duration += step.duration

            batch_key = (
                activity,
                step.parent_id if step.parent_id in parallel_parents else f"@{index}",
            )
            if batch_key not in seen_batches:
                seen_batches.add(batch_key)
                seen[activity] += 1
                rework += int(seen[activity] > 1)

        sequence = ("▶ start", *activities, "■ end")
        for index, (source, target) in enumerate(
            zip(sequence, sequence[1:], strict=False)
        ):
            edge = edges[(source, target)]
            edge["n"] += 1
            if 0 < index < len(run.steps):
                left, right = run.steps[index - 1], run.steps[index]
                edge["parallel"] += int(
                    bool(left.parent_id)
                    and left.parent_id == right.parent_id
                    and left.parent_id in parallel_parents
                )
            if target != "■ end":
                step = run.steps[index]
                edge["duration"] += step.duration
                edge["cost"] += step.cost

        bucket = variants.setdefault(activities, _VariantAccumulator())
        bucket.ids.append(run.trajectory_id)
        bucket.cost += run_cost
        bucket.duration += run_duration

    activity_stats = {
        name: ActivityStatistics(
            activity=name,
            occurrences=int(stats["n"]),
            failures=int(stats["failures"]),
            unknown_outcomes=int(stats["unknown"]),
            duration=float(stats["duration"]),
            tokens=int(stats["tokens"]),
            cost=float(stats["cost"]),
        )
        for name, stats in sorted(node.items())
    }
    transition_stats = tuple(
        TransitionStatistics(
            source=source,
            target=target,
            occurrences=int(stats["n"]),
            parallel=int(stats["parallel"]),
            duration=float(stats["duration"]),
            cost=float(stats["cost"]),
        )
        for (source, target), stats in sorted(edges.items())
    )
    variant_stats = tuple(
        TrajectoryVariant(
            activities=activities,
            trajectory_ids=tuple(sorted(bucket.ids)),
            total_cost=bucket.cost,
            total_duration=bucket.duration,
        )
        for activities, bucket in sorted(variants.items())
    )
    return TrajectoryProcess(
        activities=activity_stats,
        transitions=transition_stats,
        variants=variant_stats,
        trajectory_count=len(values),
        event_count=event_count,
        rework_events=rework,
        parallel_events=parallel_events,
        total_tokens=total_tokens,
        total_cost=total_cost,
    )
