"""Validate structured evidence, then commit a reviewable artifact revision."""

import datetime as dt

from mari_components import JsonPointer, ObjectRef, RevisionRef, ScopeRef
from mari_components.knowledge import (
    Activity,
    KnowledgeArtifact,
    LocatedEvidence,
    validate_located_evidence,
)
from mari_components.platform import InMemoryArtifactStore


def run() -> dict[str, object]:
    scope = ScopeRef(tenant="acme", space="sales")
    source = RevisionRef(
        object=ObjectRef(namespace="crm", object_id="account:42", scope=scope),
        revision="crm-v7",
    )
    material = {"plan": {"name": "enterprise", "monthly_price": 599}}
    evidence = LocatedEvidence(
        ref=source,
        locator=JsonPointer(pointer="/plan/monthly_price"),
        quote="599",
    )
    report = validate_located_evidence(
        (evidence,), resolve_material=lambda ref: material if ref == source else None
    )
    if not report.accepted:
        raise ValueError(report.issues)

    artifact = KnowledgeArtifact(
        artifact_id="fact:account-42-price",
        revision="fact-v1",
        value={"subject": "account:42", "monthly_price": 599},
        scope=scope,
        recorded_at=dt.datetime(2026, 9, 3, tzinfo=dt.UTC),
        generated_by=Activity(
            identifier="price-extractor-v1", implementation="host:model"
        ),
        evidence=(evidence,),
        derived_from=(source,),
    )
    store = InMemoryArtifactStore()
    store.commit(artifact, expected_revision=None)
    return {
        "artifact": store.get(artifact.artifact_id, scope=scope),
        "evidence": report.valid,
    }


if __name__ == "__main__":
    print(run())
