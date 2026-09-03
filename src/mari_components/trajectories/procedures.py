"""Versioned procedural candidates learned from successful tool traces."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType

from .normalize import TrajectoryStep


@dataclass(frozen=True, slots=True, kw_only=True)
class ProcedureStep:
    tool: str
    arguments: Mapping[str, str | int | float | bool | None] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if not self.tool.strip():
            raise ValueError("procedure tool is required")
        object.__setattr__(self, "arguments", MappingProxyType(dict(self.arguments)))


@dataclass(frozen=True, slots=True, kw_only=True)
class ProcedureCandidate:
    procedure_id: str
    intent: str
    steps: tuple[ProcedureStep, ...]
    source_trajectory_ids: tuple[str, ...]
    revision: str


def _lcs(left: Sequence[str], right: Sequence[str]) -> tuple[str, ...]:
    table: list[list[tuple[str, ...]]] = [
        [() for _ in range(len(right) + 1)] for _ in range(len(left) + 1)
    ]
    for i, left_value in enumerate(left, 1):
        for j, right_value in enumerate(right, 1):
            if left_value == right_value:
                table[i][j] = (*table[i - 1][j - 1], left_value)
            else:
                a, b = table[i - 1][j], table[i][j - 1]
                table[i][j] = min((a, b), key=lambda value: (-len(value), value))
    return table[-1][-1]


def learn_procedure(
    trajectories: Mapping[str, Sequence[TrajectoryStep]],
    *,
    intent: str,
) -> ProcedureCandidate:
    """Extract the stable tool subsequence shared by successful trajectories.

    This deterministic boundary does not generate code. Arguments are retained
    only when every occurrence of that shared step supplies identical safe
    normalized arguments.
    """

    if not intent.strip() or not trajectories:
        raise ValueError("intent and at least one trajectory are required")
    ordered = sorted(trajectories.items())
    if any(
        not identifier.strip() or not steps or any(not step.ok for step in steps)
        for identifier, steps in ordered
    ):
        raise ValueError(
            "source trajectories must be identified, non-empty, and successful"
        )
    tools = tuple(step.tool for step in ordered[0][1])
    for _identifier, steps in ordered[1:]:
        tools = _lcs(tools, tuple(step.tool for step in steps))
    if not tools:
        raise ValueError("successful trajectories share no procedure steps")

    occurrence_arguments: list[list[Mapping[str, str | int | float | bool | None]]] = [
        [] for _ in tools
    ]
    for _identifier, steps in ordered:
        offset = 0
        for index, tool in enumerate(tools):
            while steps[offset].tool != tool:
                offset += 1
            occurrence_arguments[index].append(steps[offset].arguments)
            offset += 1
    procedure_steps = tuple(
        ProcedureStep(
            tool=tool,
            arguments=arguments[0]
            if all(dict(value) == dict(arguments[0]) for value in arguments)
            else {},
        )
        for tool, arguments in zip(tools, occurrence_arguments, strict=True)
    )
    identity = "\0".join((intent.strip(), *(step.tool for step in procedure_steps)))
    digest = hashlib.sha256(identity.encode()).hexdigest()
    return ProcedureCandidate(
        procedure_id=f"procedure:{digest[:16]}",
        intent=intent.strip(),
        steps=procedure_steps,
        source_trajectory_ids=tuple(identifier for identifier, _steps in ordered),
        revision=f"sha256:{digest}",
    )
