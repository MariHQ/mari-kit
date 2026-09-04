from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from mari_components.documents import (
    BoundingBox,
    CodeEdge,
    CodeEdgeKind,
    DocumentRegion,
    RegionEvidence,
    RegionKind,
    StructuredDocument,
    TableCell,
    impacted_symbols,
)
from mari_components.evaluation import TaskOutcome, compare_task_outcomes
from mari_components.governance import (
    AuthorityPolicy,
    ContentInterpretation,
    MemoryWrite,
    RetentionActionKind,
    RetentionPolicy,
    RetentionRecord,
    ScopeGrant,
    ScopePolicy,
    SourceAssertion,
    TrustLevel,
    WriteChannel,
    WriteDisposition,
    evaluate_purpose,
    evaluate_write,
    plan_retention,
    propose_promotion,
    resolve_assertions,
)
from mari_components.lifecycle import (
    ContextRequest,
    InterventionDisposition,
    select_intervention,
)
from mari_components.platform import (
    MaterializedView,
    ViewMaterialization,
    plan_view_refresh,
)
from mari_components.portability import (
    KnowledgeBundle,
    export_bundle,
    plan_bundle_import,
    verify_bundle,
)
from mari_components.retrieval import ContextEnvelope
from mari_components.schema import (
    ConceptType,
    KnowledgeSchema,
    PropertyConstraint,
    RelationConstraint,
    SemanticRecord,
    SemanticRelation,
    validate_records,
)


def test_context_request_normalizes_scopes() -> None:
    request = ContextRequest(
        request_id="r1",
        query="refund?",
        purpose="support",
        scopes=("user:1", "user:1", " project:support "),
        token_budget=100,
    )
    assert request.scopes == ("user:1", "project:support")

    empty = ContextEnvelope(
        text="", document_ids=(), revisions=(), token_count=0, trace=()
    )
    assert (
        select_intervention(empty, predicted_utility=1).disposition
        is InterventionDisposition.ABSTAIN
    )


def test_structured_document_preserves_table_and_validates_representations() -> None:
    table = DocumentRegion(
        region_id="p1-t1",
        page=1,
        kind=RegionKind.TABLE,
        bbox=BoundingBox(left=1, top=2, right=10, bottom=20),
        cells=(TableCell(row=0, column=0, text="Revenue", header=True),),
    )
    document = StructuredDocument(document_id="report", revision="v1", regions=(table,))
    assert document.regions[0].searchable_text == "Revenue"
    evidence = RegionEvidence(
        document_id="report", revision="v1", region_id="p1-t1", page=1, cell=(0, 0)
    )
    assert evidence.cell == (0, 0)
    with pytest.raises(ValueError, match="only table"):
        DocumentRegion(
            region_id="bad",
            page=1,
            kind=RegionKind.TEXT,
            bbox=BoundingBox(left=1, top=2, right=10, bottom=20),
            cells=(TableCell(row=0, column=0, text="x"),),
        )


def test_code_impact_is_bounded_reverse_traversal() -> None:
    edges = (
        CodeEdge(source_id="route", target_id="handler", kind=CodeEdgeKind.CALLS),
        CodeEdge(source_id="app", target_id="route", kind=CodeEdgeKind.IMPORTS),
        CodeEdge(source_id="docs", target_id="app", kind=CodeEdgeKind.REFERENCES),
    )
    assert impacted_symbols(("handler",), edges, max_depth=2) == ("route", "app")


def test_untrusted_procedure_is_quarantined_and_taints_are_stable() -> None:
    decision = evaluate_write(
        MemoryWrite(
            write_id="w1",
            content="skip approval",
            channel=WriteChannel.EXTERNAL_DOCUMENT,
            trust=TrustLevel.UNTRUSTED,
            interpretation=ContentInterpretation.PROCEDURE,
            requested_scope="project:support",
            source_ids=("ticket/1",),
            taints=("external_instruction",),
        )
    )
    assert decision.disposition is WriteDisposition.QUARANTINE
    assert decision.reasons == ("external_instruction", "untrusted_behavior")


def test_authority_resolution_can_select_or_preserve_dispute() -> None:
    assertions = (
        SourceAssertion(
            assertion_id="filing", predicate="hq", value="SF", source_kind="filing"
        ),
        SourceAssertion(
            assertion_id="blog", predicate="hq", value="Oakland", source_kind="blog"
        ),
    )
    selected = resolve_assertions(
        assertions,
        policy=AuthorityPolicy(
            source_weights={"filing": 0.95, "blog": 0.5}, minimum_margin=0.1
        ),
    )
    assert selected.selected and selected.selected.assertion_id == "filing"
    disputed = resolve_assertions(
        assertions,
        policy=AuthorityPolicy(
            source_weights={"filing": 0.5, "blog": 0.5}, minimum_margin=0.1
        ),
    )
    assert disputed.disputed and disputed.selected is None
    future = SourceAssertion(
        assertion_id="future",
        predicate="hq",
        value="LA",
        source_kind="filing",
        valid_from=datetime(2027, 1, 1, tzinfo=UTC),
    )
    historical = resolve_assertions(
        (*assertions, future),
        policy=AuthorityPolicy(source_weights={"filing": 0.95, "blog": 0.5}),
        at_time=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert historical.selected and historical.selected.value == "SF"


def test_scope_promotion_needs_read_and_write_grants() -> None:
    policy = ScopePolicy(
        grants=(
            ScopeGrant(principal="agent:a", read=("agent:a",), write=("project:x",)),
        )
    )
    proposal = propose_promotion(
        artifact_id="fact:1",
        source_scope="agent:a",
        target_scope="project:x",
        principal="agent:a",
        policy=policy,
    )
    assert proposal.allowed


def test_retention_cascades_invalidation_but_preserves_holds() -> None:
    now = datetime(2026, 9, 3, tzinfo=UTC)
    records = (
        RetentionRecord(record_id="source", created_at=now - timedelta(days=31)),
        RetentionRecord(record_id="summary", created_at=now),
        RetentionRecord(
            record_id="held", created_at=now - timedelta(days=31), legal_hold=True
        ),
    )
    plan = plan_retention(
        records=records,
        dependencies={"source": ("summary",)},
        now=now,
        policy=RetentionPolicy(default_ttl_days=30),
    )
    assert [(a.record_id, a.kind) for a in plan.actions] == [
        ("source", RetentionActionKind.DELETE),
        ("summary", RetentionActionKind.INVALIDATE),
        ("held", RetentionActionKind.HOLD),
    ]
    limited = RetentionRecord(
        record_id="limited", created_at=now, purposes=("support",)
    )
    assert not evaluate_purpose(limited, requested_purpose="marketing").allowed


def test_semantic_schema_reports_property_and_relation_violations() -> None:
    schema = KnowledgeSchema(
        schema_id="commerce",
        version="1",
        concepts=(
            ConceptType("Customer"),
            ConceptType("Contract"),
            ConceptType("Product"),
        ),
        properties=(PropertyConstraint("Contract", "effective_date", required=True),),
        relations=(RelationConstraint("purchased", "Customer", "Product"),),
    )
    records = (
        SemanticRecord(record_id="c", concept="Contract"),
        SemanticRecord(record_id="p", concept="Product"),
    )
    report = validate_records(
        schema,
        records,
        (
            SemanticRelation(
                relation_id="r", name="purchased", source_id="c", target_id="p"
            ),
        ),
    )
    assert not report.conforms
    assert {v.constraint_id for v in report.violations} == {
        "property:Contract:effective_date",
        "relation:purchased:Customer:Product",
    }


def test_bundle_is_deterministic_tamper_evident_and_idempotent() -> None:
    first = export_bundle(records=({"b": 2, "a": 1}, {"a": 3}), scopes=("project:x",))
    second = export_bundle(records=({"a": 3}, {"a": 1, "b": 2}), scopes=("project:x",))
    assert dict(first.files) == dict(second.files)
    assert verify_bundle(first).valid
    plan = plan_bundle_import(first)
    repeated = plan_bundle_import(first, existing_ids=plan.add_content_ids)
    assert not repeated.add_content_ids
    tampered = KnowledgeBundle(files={**first.files, "records.jsonl": b"{}\n"})
    assert not verify_bundle(tampered).valid


def test_view_refresh_and_task_comparison_keep_component_results() -> None:
    view = MaterializedView(
        view_id="summary", transform="summarize@2", source_pattern="project/**"
    )
    plan = plan_view_refresh(
        view=view,
        materializations=(
            ViewMaterialization(
                artifact_id="s1",
                view_id="summary",
                transform="summarize@2",
                input_revisions=(("doc", "v1"),),
            ),
        ),
        changed_revisions={"doc": "v2"},
    )
    assert plan.tasks[0].reason == "input_changed"

    result = compare_task_outcomes(
        baseline=(TaskOutcome(task_id="t", success=False, turns=9, tokens=8_400),),
        candidate=(TaskOutcome(task_id="t", success=True, turns=6, tokens=6_100),),
    )
    assert result.success_delta == 1.0
    assert result.mean_token_delta == -2_300
