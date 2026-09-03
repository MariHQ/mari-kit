"""Evidence-bearing invariant mining from successful agent trajectories."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .process import TrajectoryRun


class TrajectoryInvariantKind(StrEnum):
    ALWAYS_CALLS = "always_calls"
    NEVER_CALLS = "never_calls"
    PRECEDES = "precedes"
    MAX_CALLS = "max_calls"
    ALWAYS_SUCCEEDS = "always_succeeds"
    ARGUMENT_DOMAIN = "argument_domain"


@dataclass(frozen=True, slots=True, kw_only=True)
class TrajectoryInvariant:
    invariant_id: str
    kind: TrajectoryInvariantKind
    tool: str
    other_tool: str = ""
    argument: str = ""
    allowed_values: tuple[str | int | float | bool | None, ...] = ()
    maximum_calls: int | None = None
    support: int
    applicable: int
    supporting_trajectory_ids: tuple[str, ...]
    counterexample_trajectory_ids: tuple[str, ...] = ()

    @property
    def support_ratio(self) -> float:
        return self.support / self.applicable if self.applicable else 0.0


@dataclass(frozen=True, slots=True, kw_only=True)
class TrajectoryInvariantViolation:
    invariant_id: str
    trajectory_id: str
    reason: str
    observed: str


def _identity(kind: TrajectoryInvariantKind, payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        {"kind": kind.value, **payload},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return f"trajectory-invariant:{hashlib.sha256(encoded.encode()).hexdigest()[:20]}"


def _candidate(
    kind: TrajectoryInvariantKind,
    *,
    tool: str,
    applicable: list[TrajectoryRun],
    supporting: list[TrajectoryRun],
    other_tool: str = "",
    argument: str = "",
    allowed_values: tuple[str | int | float | bool | None, ...] = (),
    maximum_calls: int | None = None,
) -> TrajectoryInvariant:
    payload = {
        "tool": tool,
        "other_tool": other_tool,
        "argument": argument,
        "allowed_values": allowed_values,
        "maximum_calls": maximum_calls,
    }
    support_ids = tuple(sorted(run.trajectory_id for run in supporting))
    support_set = set(support_ids)
    return TrajectoryInvariant(
        invariant_id=_identity(kind, payload),
        kind=kind,
        tool=tool,
        other_tool=other_tool,
        argument=argument,
        allowed_values=allowed_values,
        maximum_calls=maximum_calls,
        support=len(supporting),
        applicable=len(applicable),
        supporting_trajectory_ids=support_ids,
        counterexample_trajectory_ids=tuple(
            sorted(
                run.trajectory_id
                for run in applicable
                if run.trajectory_id not in support_set
            )
        ),
    )


def mine_trajectory_invariants(
    runs: Iterable[TrajectoryRun],
    *,
    available_tools: Iterable[str] = (),
    argument_names: Iterable[str] = (),
    minimum_support: float = 1.0,
    minimum_applicable: int = 2,
) -> tuple[TrajectoryInvariant, ...]:
    """Mine tool invariants from runs explicitly marked ``success``.

    ``available_tools`` is required to propose negative ``never_calls``
    candidates. Argument-domain mining is opt-in because even normalized
    arguments can carry high-cardinality or sensitive values.
    """

    if not 0 < minimum_support <= 1 or minimum_applicable < 1:
        raise ValueError("support must be in (0, 1] and applicable must be positive")
    successful = tuple(run for run in runs if run.outcome == "success")
    if len({run.trajectory_id for run in successful}) != len(successful):
        raise ValueError("successful trajectory IDs must be unique")
    tools = sorted({step.tool for run in successful for step in run.steps})
    output: list[TrajectoryInvariant] = []

    def add(candidate: TrajectoryInvariant) -> None:
        if (
            candidate.applicable >= minimum_applicable
            and candidate.support_ratio >= minimum_support
        ):
            output.append(candidate)

    for tool in tools:
        add(
            _candidate(
                TrajectoryInvariantKind.ALWAYS_CALLS,
                tool=tool,
                applicable=list(successful),
                supporting=[
                    run for run in successful if any(s.tool == tool for s in run.steps)
                ],
            )
        )
        calling = [run for run in successful if any(s.tool == tool for s in run.steps)]
        add(
            _candidate(
                TrajectoryInvariantKind.ALWAYS_SUCCEEDS,
                tool=tool,
                applicable=calling,
                supporting=[
                    run
                    for run in calling
                    if all(s.ok is True for s in run.steps if s.tool == tool)
                ],
            )
        )
        if calling:
            ceiling = max(sum(s.tool == tool for s in run.steps) for run in calling)
            add(
                _candidate(
                    TrajectoryInvariantKind.MAX_CALLS,
                    tool=tool,
                    applicable=calling,
                    supporting=calling,
                    maximum_calls=ceiling,
                )
            )

    for tool in sorted(set(available_tools) - set(tools)):
        add(
            _candidate(
                TrajectoryInvariantKind.NEVER_CALLS,
                tool=tool,
                applicable=list(successful),
                supporting=list(successful),
            )
        )

    for tool in tools:
        for other in tools:
            if tool == other:
                continue
            applicable = [
                run
                for run in successful
                if any(s.tool == tool for s in run.steps)
                and any(s.tool == other for s in run.steps)
            ]
            supporting = [
                run
                for run in applicable
                if max(i for i, s in enumerate(run.steps) if s.tool == tool)
                < min(i for i, s in enumerate(run.steps) if s.tool == other)
            ]
            add(
                _candidate(
                    TrajectoryInvariantKind.PRECEDES,
                    tool=tool,
                    other_tool=other,
                    applicable=applicable,
                    supporting=supporting,
                )
            )

    for argument in sorted(set(argument_names)):
        for tool in tools:
            applicable = [
                run
                for run in successful
                if any(s.tool == tool and argument in s.arguments for s in run.steps)
            ]
            if not applicable:
                continue
            raw_values = {
                s.arguments[argument]
                for run in applicable
                for s in run.steps
                if s.tool == tool and argument in s.arguments
            }
            allowed = tuple(
                sorted(
                    raw_values, key=lambda value: (type(value).__name__, repr(value))
                )
            )
            add(
                _candidate(
                    TrajectoryInvariantKind.ARGUMENT_DOMAIN,
                    tool=tool,
                    argument=argument,
                    allowed_values=allowed,
                    applicable=applicable,
                    supporting=applicable,
                )
            )

    return tuple(sorted(output, key=lambda item: item.invariant_id))


def check_trajectory_invariant(
    invariant: TrajectoryInvariant,
    run: TrajectoryRun,
) -> TrajectoryInvariantViolation | None:
    """Return one explainable violation, or ``None`` when it holds or is inapplicable."""

    steps = tuple(step for step in run.steps if step.tool == invariant.tool)
    reason = observed = ""
    if invariant.kind is TrajectoryInvariantKind.ALWAYS_CALLS and not steps:
        reason, observed = "required_tool_missing", "0 calls"
    elif invariant.kind is TrajectoryInvariantKind.NEVER_CALLS and steps:
        reason, observed = "forbidden_tool_present", f"{len(steps)} calls"
    elif (
        invariant.kind is TrajectoryInvariantKind.ALWAYS_SUCCEEDS
        and steps
        and any(step.ok is not True for step in steps)
    ):
        failures = sum(step.ok is False for step in steps)
        unknown = sum(step.ok is None for step in steps)
        reason, observed = (
            "tool_outcome_not_success",
            f"{failures} failures, {unknown} unknown",
        )
    elif invariant.kind is TrajectoryInvariantKind.MAX_CALLS:
        maximum = invariant.maximum_calls
        if maximum is not None and len(steps) > maximum:
            reason, observed = "call_ceiling_exceeded", f"{len(steps)} > {maximum}"
    elif invariant.kind is TrajectoryInvariantKind.PRECEDES:
        other = tuple(step for step in run.steps if step.tool == invariant.other_tool)
        if steps and other:
            left = [
                i for i, step in enumerate(run.steps) if step.tool == invariant.tool
            ]
            right = [
                i
                for i, step in enumerate(run.steps)
                if step.tool == invariant.other_tool
            ]
            if max(left) >= min(right):
                reason, observed = (
                    "tool_order_changed",
                    f"positions {left} then {right}",
                )
    elif invariant.kind is TrajectoryInvariantKind.ARGUMENT_DOMAIN:
        unexpected = [
            step.arguments[invariant.argument]
            for step in steps
            if invariant.argument in step.arguments
            and step.arguments[invariant.argument] not in invariant.allowed_values
        ]
        if unexpected:
            reason, observed = "argument_outside_observed_domain", repr(unexpected)
    if not reason:
        return None
    return TrajectoryInvariantViolation(
        invariant_id=invariant.invariant_id,
        trajectory_id=run.trajectory_id,
        reason=reason,
        observed=observed,
    )
