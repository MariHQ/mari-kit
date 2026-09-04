"""Reuse atoms across retrieval, evidence, artifacts and incremental updates."""

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass

from mari_components import (
    DependencyKey,
    DependencyStamp,
    DerivationSpec,
    LocatedEvidence,
    MaterializationReceipt,
    ObjectRef,
    RevisionRef,
    ScopeRef,
    dependency_fingerprint,
    materialization_receipt,
    plan_dependency_updates,
)
from mari_components.documents import (
    atom_collection_stamp,
    atom_dependencies,
    parse_markdown,
    semantic_atoms,
)
from mari_components.graph import trace_lineage
from mari_components.knowledge import (
    Activity,
    KnowledgeArtifact,
    validate_located_evidence,
)
from mari_components.retrieval import RetrievalUnit, RevisionBM25Index

SCOPE = ScopeRef(tenant="acme", space="support")
SOURCE = ObjectRef(namespace="document", object_id="refund-policy", scope=SCOPE)


@dataclass
class Scenario:
    sources: tuple[DependencyStamp, ...]
    specs: tuple[DerivationSpec, ...]
    builders: dict[DependencyKey, Callable[[], object]]
    units: tuple[RetrievalUnit, ...]
    artifact: KnowledgeArtifact
    policy: str


def scenario(
    text: str, revision: str, *, policy: str = "allowed", model: str = "fixture:v1"
) -> Scenario:
    atoms = semantic_atoms(
        parse_markdown(text, artifact_id=SOURCE.object_id, revision=revision).values[0]
    )
    inputs = [atom_dependencies(atom, source=SOURCE) for atom in atoms]
    membership = atom_collection_stamp(atoms, source=SOURCE)
    access = DependencyStamp(
        dependency=DependencyKey(object=SOURCE, aspect="access"),
        fingerprint=dependency_fingerprint(policy),
    )
    source_revision = DependencyStamp.from_revision(
        RevisionRef(object=SOURCE, revision=revision)
    )
    sources = (
        *[stamp for item in inputs for stamp in item.stamps],
        membership,
        access,
        source_revision,
    )
    specs: dict[DependencyKey, DerivationSpec] = {}
    builders: dict[DependencyKey, Callable[[], object]] = {}
    vectors: list[DependencyKey] = []
    for atom, item in zip(atoms, inputs, strict=True):
        output = DependencyKey(
            object=SOURCE, unit_id=item.content.fingerprint, aspect="raw_vector"
        )
        vectors.append(output)
        specs[output] = DerivationSpec(
            output=output,
            inputs=(item.content.dependency,),
            implementation="embedding:v1",
            configuration={"model": model},
        )
        # A deterministic fixture callback, supplied by the host in production.
        builders[output] = lambda text=atom.text: [
            len(text),
            text.casefold().count("refund"),
        ]

    evidence = tuple(atom.located_evidence(source=SOURCE) for atom in atoms)
    report = validate_located_evidence(
        evidence,
        resolve_material=lambda ref: (
            text if ref.object == SOURCE and ref.revision == revision else None
        ),
    )
    assert not report.issues
    artifact = KnowledgeArtifact(
        artifact_id="policy-summary",
        revision=dependency_fingerprint(
            {"text": text, "source_revision": revision, "recipe": "extract:v1"}
        ),
        value={"passages": [atom.text for atom in atoms]},
        scope=SCOPE,
        recorded_at=dt.datetime(2026, 9, 4, tzinfo=dt.UTC),
        generated_by=Activity(
            identifier="fixture-extraction", implementation="extract:v1"
        ),
        evidence=evidence,
        derived_from=tuple(item.ref for item in evidence),
    )
    knowledge_spec = artifact.derivation_spec(
        inputs=(
            membership.dependency,
            source_revision.dependency,
            *(item.binding.dependency for item in inputs),
        )
    )
    specs[knowledge_spec.output] = knowledge_spec
    builders[knowledge_spec.output] = lambda: artifact

    units = tuple(RetrievalUnit.from_atom(atom, source=SOURCE) for atom in atoms)
    projection = DependencyKey(object=SOURCE, aspect="search_projection")
    specs[projection] = DerivationSpec(
        output=projection,
        inputs=tuple(
            dict.fromkeys(
                (
                    membership.dependency,
                    access.dependency,
                    *vectors,
                    *(item.binding.dependency for item in inputs),
                )
            )
        ),
        implementation="search-projection:v1",
    )
    # Policy version changes invalidate the projection. The host still authorizes
    # the actual query below; a version fingerprint is never an access grant.
    builders[projection] = lambda: {"units": units, "policy": policy}
    return Scenario(
        sources=sources,
        specs=tuple(specs.values()),
        builders=builders,
        units=units,
        artifact=artifact,
        policy=policy,
    )


def materialize(
    current: Scenario,
    receipts: dict[DependencyKey, MaterializationReceipt],
    values: dict[DependencyKey, object],
) -> tuple[DependencyKey, ...]:
    """Example host execution, recording receipts only after successful builds."""
    rebuilt: list[DependencyKey] = []
    by_output = {spec.output: spec for spec in current.specs}
    while True:
        plan = plan_dependency_updates(
            sources=current.sources,
            derivations=current.specs,
            materializations=receipts.values(),
        )
        if not plan.ready:
            assert len(plan.reusable) == len(current.specs), plan.updates
            return tuple(rebuilt)
        for update in plan.ready:
            value = current.builders[update.output]()
            fingerprint = (
                value.revision
                if isinstance(value, KnowledgeArtifact)
                else dependency_fingerprint(value)
            )
            receipt = materialization_receipt(
                by_output[update.output], update.inputs, output_fingerprint=fingerprint
            )
            # A production adapter commits the value and receipt in one transaction,
            # conditional on the input snapshot still being current.
            values[update.output], receipts[update.output] = value, receipt
            rebuilt.append(update.output)


def run() -> dict[str, object]:
    before = scenario("# Policy\n\nRefunds within 30 days.\n\nContact support.\n", "v1")
    after = scenario("# Policy\n\nRefunds within 14 days.\n\nContact support.\n", "v2")
    receipts: dict[DependencyKey, MaterializationReceipt] = {}
    values: dict[DependencyKey, object] = {}
    materialize(before, receipts, values)
    rebuilt = materialize(after, receipts, values)
    clean_receipts: dict[DependencyKey, MaterializationReceipt] = {}
    clean_values: dict[DependencyKey, object] = {}
    materialize(after, clean_receipts, clean_values)
    equivalent = all(
        values[key] == value and receipts[key] == clean_receipts[key]
        for key, value in clean_values.items()
    )

    units = {unit.ref.to_revision_ref(): unit.text for unit in after.units}
    index = RevisionBM25Index(units)
    allowed_refs = set(units) if after.policy == "allowed" else set()
    hits = index.search("refunds", limit=1, allowed_refs=allowed_refs)
    matching_evidence = tuple(
        item
        for item in after.artifact.evidence
        if isinstance(item, LocatedEvidence) and item.ref == hits[0].ref
    )
    by_output = {spec.output: spec for spec in after.specs}
    lineage = trace_lineage(
        after.artifact.derivation_spec(inputs=()).output,
        parents=lambda key: by_output[key].inputs if key in by_output else (),
    )
    return {
        "incremental_equals_rebuild": equivalent,
        "vectors_rebuilt": sum(key.aspect == "raw_vector" for key in rebuilt),
        "retrieved_current_evidence": bool(
            matching_evidence and "14 days" in matching_evidence[0].quote
        ),
        "lineage_reaches_atom_inputs": len(lineage.visits) > 1,
    }


if __name__ == "__main__":
    print(run())
