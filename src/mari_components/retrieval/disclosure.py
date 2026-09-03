"""Conditional and progressive disclosure over caller-owned knowledge."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import Any


class DisclosureOperator(StrEnum):
    EXISTS = "exists"
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    IN = "in"


@dataclass(frozen=True, slots=True, kw_only=True)
class DisclosureCondition:
    field: str
    operator: DisclosureOperator
    value: object = None

    def __post_init__(self) -> None:
        if not self.field.strip():
            raise ValueError("disclosure condition field is required")


@dataclass(frozen=True, slots=True, kw_only=True)
class DisclosureRule:
    rule_id: str
    conditions: tuple[DisclosureCondition, ...]
    require_all: bool = True

    def __post_init__(self) -> None:
        if not self.rule_id.strip() or not self.conditions:
            raise ValueError("disclosure rule identity and conditions are required")
        object.__setattr__(self, "conditions", tuple(self.conditions))


@dataclass(frozen=True, slots=True, kw_only=True)
class DisclosureDecision:
    rule_id: str
    eligible: bool
    condition_results: tuple[bool, ...]


def evaluate_disclosure(
    rule: DisclosureRule, facts: Mapping[str, Any]
) -> DisclosureDecision:
    """Evaluate content relevance conditions; this is not authorization."""

    results = tuple(
        _condition_matches(condition, facts) for condition in rule.conditions
    )
    return DisclosureDecision(
        rule_id=rule.rule_id,
        eligible=all(results) if rule.require_all else any(results),
        condition_results=results,
    )


def _condition_matches(
    condition: DisclosureCondition, facts: Mapping[str, Any]
) -> bool:
    present = condition.field in facts
    observed = facts.get(condition.field)
    if condition.operator is DisclosureOperator.EXISTS:
        return present
    if condition.operator is DisclosureOperator.EQUALS:
        return present and observed == condition.value
    if condition.operator is DisclosureOperator.NOT_EQUALS:
        return present and observed != condition.value
    if condition.operator is DisclosureOperator.IN:
        expected = condition.value
        return (
            present
            and isinstance(expected, (tuple, list, set, frozenset))
            and observed in expected
        )
    raise AssertionError("unreachable disclosure operator")


class DisclosureLevel(IntEnum):
    INDEX = 0
    SUMMARY = 1
    SECTION = 2
    SOURCE = 3


@dataclass(frozen=True, slots=True, kw_only=True)
class DisclosureUnit:
    unit_id: str
    artifact_id: str
    revision: str
    level: DisclosureLevel
    text: str
    token_count: int
    expands_to: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (
            not all(
                value.strip()
                for value in (self.unit_id, self.artifact_id, self.revision, self.text)
            )
            or self.token_count < 1
        ):
            raise ValueError("disclosure units require identity, text, and token count")
        object.__setattr__(self, "expands_to", tuple(self.expands_to))


class DisclosureManifestIssueKind(StrEnum):
    DUPLICATE_UNIT = "duplicate_unit"
    MISSING_TARGET = "missing_target"
    NON_INCREASING_LEVEL = "non_increasing_level"
    CROSS_REVISION_TARGET = "cross_revision_target"
    EXPANSION_CYCLE = "expansion_cycle"


@dataclass(frozen=True, slots=True, kw_only=True)
class DisclosureManifestIssue:
    kind: DisclosureManifestIssueKind
    unit_id: str
    target_id: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class ProgressiveDisclosureManifest:
    units: tuple[DisclosureUnit, ...]
    root_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class DisclosureManifestReport:
    issues: tuple[DisclosureManifestIssue, ...]
    total_tokens: int

    @property
    def valid(self) -> bool:
        return not self.issues


@dataclass(frozen=True, slots=True, kw_only=True)
class DisclosureSelection:
    selected: tuple[DisclosureUnit, ...]
    skipped_ids: tuple[str, ...]
    token_count: int
    truncated: bool


def inspect_disclosure_manifest(
    manifest: ProgressiveDisclosureManifest,
) -> DisclosureManifestReport:
    """Validate identity, revision continuity, increasing detail, and acyclicity."""

    counts: dict[str, int] = {}
    for unit in manifest.units:
        counts[unit.unit_id] = counts.get(unit.unit_id, 0) + 1
    by_id = {unit.unit_id: unit for unit in manifest.units}
    issues: list[DisclosureManifestIssue] = []
    for unit_id, count in counts.items():
        if count > 1:
            issues.append(
                DisclosureManifestIssue(
                    kind=DisclosureManifestIssueKind.DUPLICATE_UNIT, unit_id=unit_id
                )
            )
    for unit in manifest.units:
        for target_id in unit.expands_to:
            target = by_id.get(target_id)
            if target is None:
                issues.append(
                    DisclosureManifestIssue(
                        kind=DisclosureManifestIssueKind.MISSING_TARGET,
                        unit_id=unit.unit_id,
                        target_id=target_id,
                    )
                )
            elif (
                target.artifact_id != unit.artifact_id
                or target.revision != unit.revision
            ):
                issues.append(
                    DisclosureManifestIssue(
                        kind=DisclosureManifestIssueKind.CROSS_REVISION_TARGET,
                        unit_id=unit.unit_id,
                        target_id=target_id,
                    )
                )
            elif target.level <= unit.level:
                issues.append(
                    DisclosureManifestIssue(
                        kind=DisclosureManifestIssueKind.NON_INCREASING_LEVEL,
                        unit_id=unit.unit_id,
                        target_id=target_id,
                    )
                )
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(unit_id: str) -> None:
        if unit_id in visiting:
            issues.append(
                DisclosureManifestIssue(
                    kind=DisclosureManifestIssueKind.EXPANSION_CYCLE, unit_id=unit_id
                )
            )
            return
        if unit_id in visited or unit_id not in by_id:
            return
        visiting.add(unit_id)
        for target_id in by_id[unit_id].expands_to:
            visit(target_id)
        visiting.remove(unit_id)
        visited.add(unit_id)

    for root_id in manifest.root_ids:
        if root_id not in by_id:
            issues.append(
                DisclosureManifestIssue(
                    kind=DisclosureManifestIssueKind.MISSING_TARGET,
                    unit_id="",
                    target_id=root_id,
                )
            )
        visit(root_id)
    unique = {(item.kind, item.unit_id, item.target_id): item for item in issues}
    return DisclosureManifestReport(
        issues=tuple(
            unique[key] for key in sorted(unique, key=lambda row: tuple(map(str, row)))
        ),
        total_tokens=sum(unit.token_count for unit in manifest.units),
    )


def expand_disclosure(
    manifest: ProgressiveDisclosureManifest,
    *,
    root_ids: Iterable[str] | None = None,
    maximum_level: DisclosureLevel = DisclosureLevel.SOURCE,
    token_budget: int,
) -> DisclosureSelection:
    """Breadth-first expansion under a budget, without relevance or ACL decisions."""

    if token_budget < 0:
        raise ValueError("token budget must not be negative")
    report = inspect_disclosure_manifest(manifest)
    if not report.valid:
        raise ValueError("progressive disclosure manifest is invalid")
    by_id = {unit.unit_id: unit for unit in manifest.units}
    queue = deque(root_ids if root_ids is not None else manifest.root_ids)
    selected: list[DisclosureUnit] = []
    skipped: list[str] = []
    seen: set[str] = set()
    used = 0
    while queue:
        unit_id = queue.popleft()
        if unit_id in seen:
            continue
        seen.add(unit_id)
        unit = by_id.get(unit_id)
        if unit is None:
            raise ValueError("requested disclosure root is unknown")
        if unit.level > maximum_level or used + unit.token_count > token_budget:
            skipped.append(unit_id)
            continue
        selected.append(unit)
        used += unit.token_count
        queue.extend(unit.expands_to)
    return DisclosureSelection(
        selected=tuple(selected),
        skipped_ids=tuple(skipped),
        token_count=used,
        truncated=bool(skipped),
    )
