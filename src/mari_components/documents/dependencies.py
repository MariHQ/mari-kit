"""Semantic atoms as shared, scoped inputs to any Mari derivation."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from mari_components.dependencies import (
    DependencyKey,
    DependencyStamp,
    dependency_fingerprint,
)
from mari_components.references import ObjectRef

from .atoms import SemanticAtom


@dataclass(frozen=True, slots=True, kw_only=True)
class AtomDependencies:
    content: DependencyStamp
    context: DependencyStamp
    binding: DependencyStamp
    revision: DependencyStamp

    @property
    def stamps(self) -> tuple[DependencyStamp, ...]:
        return self.content, self.context, self.binding, self.revision


def atom_dependencies(atom: SemanticAtom, *, source: ObjectRef) -> AtomDependencies:
    """Separate reusable text from its current revision and source coordinates.

    Text keys are content-addressed within the source scope. Moving or duplicating
    identical text can reuse a representation, while bindings remain occurrence
    specific. Exact text is fingerprinted: the atom's normalized alignment hash is
    insufficient to prove identical embedding input.
    """
    ref = atom.to_revision_ref(source=source)
    content = dependency_fingerprint(atom.text)
    context = dependency_fingerprint(atom.contextual_text)
    return AtomDependencies(
        content=DependencyStamp(
            dependency=DependencyKey(
                object=source, unit_id=content, aspect="atom_text"
            ),
            fingerprint=content,
        ),
        context=DependencyStamp(
            dependency=DependencyKey(
                object=source, unit_id=context, aspect="atom_context"
            ),
            fingerprint=context,
        ),
        binding=DependencyStamp(
            dependency=DependencyKey(
                object=source, unit_id=atom.atom_id, aspect="atom_binding"
            ),
            fingerprint=dependency_fingerprint(
                {
                    "ref": ref,
                    "section": atom.section_id,
                    "ordinal": atom.ordinal,
                    "start": atom.start,
                    "end": atom.end,
                    "content": content,
                    "context": context,
                }
            ),
        ),
        revision=DependencyStamp.from_revision(ref),
    )


def atom_collection_stamp(
    atoms: Iterable[SemanticAtom], *, source: ObjectRef, unit_id: str = ""
) -> DependencyStamp:
    """Track ordered membership for a document, section, or selected atom set.

    Include this input in summaries and projections that must notice newly added
    atoms. Callers supply the complete ordered collection, including an empty one.
    """
    values = tuple(atoms)
    if len({atom.atom_id for atom in values}) != len(values):
        raise ValueError("atom collection IDs must be unique")
    if len({atom.source_revision for atom in values}) > 1:
        raise ValueError("atom collection must belong to one source revision")
    for atom in values:
        atom.to_revision_ref(source=source)
    return DependencyStamp(
        dependency=DependencyKey(
            object=source, unit_id=unit_id, aspect="atom_membership"
        ),
        fingerprint=dependency_fingerprint(
            [
                (atom.atom_id, atom.section_id, atom.text, atom.contextual_text)
                for atom in values
            ]
        ),
    )
