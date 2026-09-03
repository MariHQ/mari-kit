"""Small backend-neutral semantic-schema kernel."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True, slots=True)
class ConceptType:
    name: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("concept name is required")


@dataclass(frozen=True, slots=True)
class PropertyConstraint:
    concept: str
    property_name: str
    required: bool = False
    minimum_count: int = 0
    maximum_count: int | None = None

    @property
    def constraint_id(self) -> str:
        return f"property:{self.concept}:{self.property_name}"


@dataclass(frozen=True, slots=True)
class RelationConstraint:
    name: str
    source: str
    target: str

    @property
    def constraint_id(self) -> str:
        return f"relation:{self.name}:{self.source}:{self.target}"


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeSchema:
    schema_id: str
    version: str
    concepts: tuple[ConceptType, ...]
    properties: tuple[PropertyConstraint, ...] = ()
    relations: tuple[RelationConstraint, ...] = ()

    def __post_init__(self) -> None:
        if not self.schema_id or not self.version:
            raise ValueError("schema ID and version are required")
        names = [item.name for item in self.concepts]
        if len(names) != len(set(names)):
            raise ValueError("concept names must be unique")
        unknown = {
            name
            for constraint in self.relations
            for name in (constraint.source, constraint.target)
            if name not in names
        } | {constraint.concept for constraint in self.properties if constraint.concept not in names}
        if unknown:
            raise ValueError(f"constraints reference unknown concepts: {sorted(unknown)}")


@dataclass(frozen=True, slots=True, kw_only=True)
class SemanticRecord:
    record_id: str
    concept: str
    properties: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "properties", MappingProxyType(dict(self.properties)))


@dataclass(frozen=True, slots=True, kw_only=True)
class SemanticRelation:
    relation_id: str
    name: str
    source_id: str
    target_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class SchemaViolation:
    focus_id: str
    constraint_id: str
    message: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ValidationReport:
    conforms: bool
    violations: tuple[SchemaViolation, ...]


def validate_records(
    schema: KnowledgeSchema,
    records: Iterable[SemanticRecord],
    relations: Iterable[SemanticRelation] = (),
) -> ValidationReport:
    """Validate the common required/cardinality/domain/range subset."""

    values = tuple(records)
    by_id = {value.record_id: value for value in values}
    concepts = {item.name for item in schema.concepts}
    violations: list[SchemaViolation] = []
    for record in values:
        if record.concept not in concepts:
            violations.append(SchemaViolation(focus_id=record.record_id, constraint_id="known_concept", message=f"unknown concept {record.concept}"))
            continue
        for constraint in schema.properties:
            if constraint.concept != record.concept:
                continue
            raw = record.properties.get(constraint.property_name)
            count = len(raw) if isinstance(raw, (tuple, list, set)) else int(raw is not None)
            minimum = max(constraint.minimum_count, int(constraint.required))
            if count < minimum or (constraint.maximum_count is not None and count > constraint.maximum_count):
                violations.append(SchemaViolation(focus_id=record.record_id, constraint_id=constraint.constraint_id, message=f"observed cardinality {count}"))
    constraints = {item.name: item for item in schema.relations}
    for relation in relations:
        constraint = constraints.get(relation.name)
        source = by_id.get(relation.source_id)
        target = by_id.get(relation.target_id)
        if constraint is None:
            violations.append(SchemaViolation(focus_id=relation.relation_id, constraint_id="known_relation", message=f"unknown relation {relation.name}"))
        elif source is None or target is None or source.concept != constraint.source or target.concept != constraint.target:
            violations.append(SchemaViolation(focus_id=relation.relation_id, constraint_id=constraint.constraint_id, message="relation domain or range does not conform"))
    return ValidationReport(conforms=not violations, violations=tuple(violations))
