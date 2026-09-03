from __future__ import annotations

from mari_components.knowledge import (
    DerivationInput,
    DerivationIssueKind,
    KnowledgeDerivation,
    KnowledgeEdit,
    KnowledgeObservation,
    KnowledgeObservationStage,
    KnowledgeOrigin,
    ObservationIssueKind,
    inspect_knowledge_derivations,
    inspect_knowledge_observations,
    validate_knowledge_changeset,
)
from mari_components.knowledge.artifacts import ArtifactRef
from mari_components.retrieval import (
    DisclosureCondition,
    DisclosureLevel,
    DisclosureOperator,
    DisclosureRule,
    DisclosureUnit,
    ProgressiveDisclosureManifest,
    evaluate_disclosure,
    expand_disclosure,
    inspect_disclosure_manifest,
)
from mari_components.types import KnowledgeDocument


def _ref(identifier: str, revision: str = "r1") -> ArtifactRef:
    return ArtifactRef(artifact_id=identifier, revision=revision)


def test_observation_ledger_does_not_infer_use_from_retrieval_or_citation() -> None:
    observations = (
        KnowledgeObservation(
            observation_id="1",
            activity_id="answer-1",
            artifact_id="policy",
            revision="r7",
            stage=KnowledgeObservationStage.RETRIEVED,
            ordinal=0,
        ),
        KnowledgeObservation(
            observation_id="2",
            activity_id="answer-1",
            artifact_id="policy",
            revision="r7",
            stage=KnowledgeObservationStage.SHOWN,
            ordinal=1,
        ),
        KnowledgeObservation(
            observation_id="3",
            activity_id="answer-1",
            artifact_id="policy",
            revision="r7",
            stage=KnowledgeObservationStage.CITED,
            ordinal=2,
        ),
    )
    report = inspect_knowledge_observations(observations)
    assert report.valid
    assert report.cited == (("policy", "r7"),)
    assert report.used == ()

    missing = inspect_knowledge_observations(
        [
            KnowledgeObservation(
                observation_id="4",
                activity_id="answer-2",
                artifact_id="policy",
                revision="r7",
                stage=KnowledgeObservationStage.USED,
                ordinal=0,
            )
        ]
    )
    assert missing.issues[0].kind is ObservationIssueKind.MISSING_PREDECESSOR


def test_derivation_audit_detects_generated_evidence_claimed_as_independent() -> None:
    source = KnowledgeDerivation(output=_ref("source"), origin=KnowledgeOrigin.SOURCE)
    summary = KnowledgeDerivation(
        output=_ref("summary"),
        origin=KnowledgeOrigin.DERIVED,
        inputs=(DerivationInput(ref=source.output),),
    )
    recycled = KnowledgeDerivation(
        output=_ref("recycled"),
        origin=KnowledgeOrigin.DERIVED,
        inputs=(DerivationInput(ref=summary.output, claimed_independent=True),),
    )
    report = inspect_knowledge_derivations([source, summary, recycled])
    assert not report.valid
    assert DerivationIssueKind.DERIVED_AS_INDEPENDENT in {
        issue.kind for issue in report.issues
    }
    assert report.source_roots == (source.output,)


def test_conditional_disclosure_is_a_predicate_not_an_acl() -> None:
    rule = DisclosureRule(
        rule_id="incident-only",
        conditions=(
            DisclosureCondition(
                field="task_kind",
                operator=DisclosureOperator.EQUALS,
                value="incident",
            ),
            DisclosureCondition(
                field="severity",
                operator=DisclosureOperator.IN,
                value=("sev0", "sev1"),
            ),
        ),
    )
    assert evaluate_disclosure(
        rule, {"task_kind": "incident", "severity": "sev1"}
    ).eligible
    assert not evaluate_disclosure(
        rule, {"task_kind": "support", "severity": "sev1"}
    ).eligible


def test_changeset_builds_cross_document_previews_and_inverse_edits() -> None:
    documents = {
        "docs/a": KnowledgeDocument(
            source_id="docs",
            external_id="a",
            title="A",
            body="Limit is 10.",
            revision="r1",
        ),
        "docs/b": KnowledgeDocument(
            source_id="docs",
            external_id="b",
            title="B",
            body="Route to basic.",
            revision="r2",
        ),
    }
    result = validate_knowledge_changeset(
        documents,
        [
            KnowledgeEdit(
                document_id="docs/a",
                source_revision="r1",
                original="10",
                replacement="20",
                reason="Correct the enterprise limit",
            ),
            KnowledgeEdit(
                document_id="docs/b",
                source_revision="r2",
                original="basic",
                replacement="enterprise",
                reason="Keep routing consistent",
            ),
        ],
    )
    assert result.valid
    assert [entry.preview for entry in result.entries] == [
        "Limit is 20.",
        "Route to enterprise.",
    ]
    assert (
        result.entries[0].inverse_edits[0].source_revision
        == result.entries[0].proposed_revision
    )


def test_progressive_disclosure_expands_detail_under_budget() -> None:
    units = (
        DisclosureUnit(
            unit_id="idx",
            artifact_id="policy",
            revision="r7",
            level=DisclosureLevel.INDEX,
            text="Plan limits",
            token_count=2,
            expands_to=("summary",),
        ),
        DisclosureUnit(
            unit_id="summary",
            artifact_id="policy",
            revision="r7",
            level=DisclosureLevel.SUMMARY,
            text="Limits vary by plan.",
            token_count=5,
            expands_to=("source",),
        ),
        DisclosureUnit(
            unit_id="source",
            artifact_id="policy",
            revision="r7",
            level=DisclosureLevel.SOURCE,
            text="Enterprise accounts are limited to 20 seats.",
            token_count=10,
        ),
    )
    manifest = ProgressiveDisclosureManifest(units=units, root_ids=("idx",))
    assert inspect_disclosure_manifest(manifest).valid
    small = expand_disclosure(manifest, token_budget=7)
    assert tuple(unit.unit_id for unit in small.selected) == ("idx", "summary")
    assert small.skipped_ids == ("source",)
    full = expand_disclosure(manifest, token_budget=17)
    assert tuple(unit.unit_id for unit in full.selected) == (
        "idx",
        "summary",
        "source",
    )
