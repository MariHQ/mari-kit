"""Hard regression gates for benchmark reports."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum


class GateMode(StrEnum):
    AT_LEAST = "at_least"
    AT_MOST = "at_most"
    NO_REGRESSION = "no_regression"


@dataclass(frozen=True, slots=True, kw_only=True)
class MetricGate:
    metric: str
    mode: GateMode
    value: float = 0.0
    tolerance: float = 0.0

    def __post_init__(self) -> None:
        if (
            not self.metric.strip()
            or not all(math.isfinite(value) for value in (self.value, self.tolerance))
            or self.tolerance < 0
        ):
            raise ValueError(
                "gates require a metric and finite value/non-negative tolerance"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class GateCheck:
    metric: str
    passed: bool
    observed: float
    required: float
    mode: GateMode


@dataclass(frozen=True, slots=True, kw_only=True)
class GateReport:
    passed: bool
    checks: tuple[GateCheck, ...]


def regression_gate(
    candidate: Mapping[str, float],
    *,
    gates: Iterable[MetricGate],
    baseline: Mapping[str, float] | None = None,
) -> GateReport:
    """Evaluate independent hard constraints without hiding failed metrics."""

    checks: list[GateCheck] = []
    for gate in gates:
        if gate.metric not in candidate:
            raise ValueError(f"candidate omitted metric {gate.metric!r}")
        observed = float(candidate[gate.metric])
        if not math.isfinite(observed):
            raise ValueError("candidate metrics must be finite")
        if gate.mode is GateMode.NO_REGRESSION:
            if baseline is None or gate.metric not in baseline:
                raise ValueError(f"baseline omitted metric {gate.metric!r}")
            required = float(baseline[gate.metric]) - gate.tolerance
            passed = observed >= required
        elif gate.mode is GateMode.AT_LEAST:
            required = gate.value
            passed = observed + gate.tolerance >= required
        else:
            required = gate.value
            passed = observed - gate.tolerance <= required
        checks.append(
            GateCheck(
                metric=gate.metric,
                passed=passed,
                observed=observed,
                required=required,
                mode=gate.mode,
            )
        )
    return GateReport(
        passed=all(check.passed for check in checks), checks=tuple(checks)
    )
