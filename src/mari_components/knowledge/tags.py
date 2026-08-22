"""Workspace-defined document tags and retrieval behavior."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

_TAG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def normalize_tag(value: str) -> str:
    tag = re.sub(r"[^a-z0-9-]", "", value.strip().lower())
    tag = re.sub(r"-+", "-", tag).strip("-")
    if not tag or not _TAG_RE.fullmatch(tag):
        raise ValueError("tag must contain lowercase letters, numbers, or hyphens")
    return tag


@dataclass(frozen=True, slots=True, kw_only=True)
class TagDefinition:
    key: str
    label: str
    kind: str = "neutral"
    search_weight: float = 1.0
    behaviors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", normalize_tag(self.key))
        if not self.label.strip() or not self.kind.strip():
            raise ValueError("tag label and kind are required")
        if not math.isfinite(self.search_weight) or self.search_weight < 0:
            raise ValueError("tag search_weight must be finite and non-negative")
        object.__setattr__(
            self, "behaviors", tuple(x.strip() for x in self.behaviors if x.strip())
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class TagAssignments:
    """Mari-managed tags keyed by canonical document ID.

    Assignments intentionally live outside connector-owned documents so a
    provider resync cannot erase workspace curation.
    """

    by_document: Mapping[str, frozenset[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalized: dict[str, frozenset[str]] = {}
        for document_id, tags in self.by_document.items():
            if not document_id.strip():
                raise ValueError("tag assignment document IDs are required")
            normalized[document_id] = frozenset(normalize_tag(tag) for tag in tags)
        object.__setattr__(self, "by_document", MappingProxyType(normalized))

    def tags_for(self, document_id: str) -> frozenset[str]:
        return self.by_document.get(document_id, frozenset())


def assign_tags(
    assignments: TagAssignments,
    document_id: str,
    definitions: Mapping[str, TagDefinition],
    *,
    add: Iterable[str] = (),
    remove: Iterable[str] = (),
) -> TagAssignments:
    """Return updated workspace assignments without changing source data."""
    if not document_id.strip():
        raise ValueError("document_id is required")
    added = {normalize_tag(value) for value in add}
    removed = {normalize_tag(value) for value in remove}
    unknown = added - set(definitions)
    if unknown:
        raise KeyError(f"undefined tags: {sorted(unknown)!r}")
    updated = dict(assignments.by_document)
    tags = (set(assignments.tags_for(document_id)) | added) - removed
    if tags:
        updated[document_id] = frozenset(tags)
    else:
        updated.pop(document_id, None)
    return TagAssignments(by_document=updated)


def search_weight(
    document_id: str,
    assignments: TagAssignments,
    definitions: Mapping[str, TagDefinition],
) -> float:
    """Use the strongest assigned tag weight, matching Mari Cloud ranking semantics."""
    return max(
        (
            definitions[tag].search_weight
            for tag in assignments.tags_for(document_id)
            if tag in definitions
        ),
        default=1.0,
    )
