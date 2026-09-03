"""Constraint-first search over externally evaluated knowledge configurations."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any


class ObjectiveDirection(StrEnum):
    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"


@dataclass(frozen=True, slots=True, kw_only=True)
class MetricObjective:
    name: str
    direction: ObjectiveDirection
    weight: float = 1.0
    minimum: float | None = None
    maximum: float | None = None

    def __post_init__(self) -> None:
        if not self.name.strip() or not math.isfinite(self.weight) or self.weight < 0:
            raise ValueError(
                "objective name and non-negative finite weight are required"
            )
        if self.minimum is not None and not math.isfinite(self.minimum):
            raise ValueError("objective minimum must be finite")
        if self.maximum is not None and not math.isfinite(self.maximum):
            raise ValueError("objective maximum must be finite")
        if (
            self.minimum is not None
            and self.maximum is not None
            and self.minimum > self.maximum
        ):
            raise ValueError("objective minimum cannot exceed maximum")


@dataclass(frozen=True, slots=True, kw_only=True)
class CompileCandidate:
    fingerprint: str
    configuration: Mapping[str, Any]
    metrics: Mapping[str, float]
    feasible: bool
    violations: tuple[str, ...]
    utility: float


@dataclass(frozen=True, slots=True, kw_only=True)
class CompileResult:
    configuration: Mapping[str, Any]
    winner: CompileCandidate
    candidates: tuple[CompileCandidate, ...]


def compile_configurations(
    configurations: Iterable[Mapping[str, Any]],
    *,
    evaluate: Callable[[Mapping[str, Any]], Mapping[str, float]],
    objectives: Iterable[MetricObjective],
) -> CompileResult:
    """Evaluate once, reject hard violations, then select weighted utility."""

    objective_values = tuple(objectives)
    if not objective_values:
        raise ValueError("at least one objective is required")
    names = [value.name for value in objective_values]
    if len(names) != len(set(names)):
        raise ValueError("objective names must be unique")
    candidates: list[CompileCandidate] = []
    fingerprints: set[str] = set()
    for raw_config in configurations:
        config = dict(raw_config)
        encoded = json.dumps(
            config, sort_keys=True, separators=(",", ":"), default=str
        ).encode()
        fingerprint = hashlib.sha256(encoded).hexdigest()
        if fingerprint in fingerprints:
            continue
        fingerprints.add(fingerprint)
        observed = {
            name: float(value)
            for name, value in evaluate(MappingProxyType(config)).items()
        }
        missing = set(names) - set(observed)
        if missing:
            raise ValueError(f"evaluator omitted objectives: {sorted(missing)!r}")
        if any(not math.isfinite(observed[name]) for name in names):
            raise ValueError("evaluator metrics must be finite")
        violations = tuple(
            reason
            for objective in objective_values
            for reason in (
                (
                    f"{objective.name} below minimum"
                    if objective.minimum is not None
                    and observed[objective.name] < objective.minimum
                    else ""
                ),
                (
                    f"{objective.name} above maximum"
                    if objective.maximum is not None
                    and observed[objective.name] > objective.maximum
                    else ""
                ),
            )
            if reason
        )
        utility = sum(
            objective.weight
            * observed[objective.name]
            * (1 if objective.direction is ObjectiveDirection.MAXIMIZE else -1)
            for objective in objective_values
        )
        candidates.append(
            CompileCandidate(
                fingerprint=fingerprint,
                configuration=MappingProxyType(config),
                metrics=MappingProxyType(observed),
                feasible=not violations,
                violations=violations,
                utility=utility,
            )
        )
    feasible = [value for value in candidates if value.feasible]
    if not feasible:
        raise ValueError("no configuration satisfies all hard constraints")
    winner = sorted(feasible, key=lambda value: (-value.utility, value.fingerprint))[0]
    return CompileResult(
        configuration=winner.configuration,
        winner=winner,
        candidates=tuple(sorted(candidates, key=lambda value: value.fingerprint)),
    )
