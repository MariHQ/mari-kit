from __future__ import annotations

from datetime import UTC, datetime

import pytest

from mari_components.connectors import hydrate_hints
from mari_components.documents import ParsedBlock, ParsedDocument
from mari_components.evaluation import evaluate_graph_context
from mari_components.graph import (
    LineageEdge,
    TimeInterval,
    build_adjacency,
    close_interval,
    cluster_matches,
    diff_records,
    explain_candidate_pairs,
    inspect_clusters,
    interval_contains,
    predecessor_dag,
    resolve_relation_evidence,
    trace_lineage_edges,
)
from mari_components.knowledge import (
    ArtifactEvidence,
    ArtifactRef,
    Assertion,
    AssertionUpdateKind,
    EvidenceIssueKind,
    all_of,
    group_assertions,
    plan_assertion_update,
    valid_at,
    validate_artifact_evidence,
)
from mari_components.retrieval import (
    BM25Index,
    ContextItem,
    IndexDelta,
    IndexOperation,
    RetrievalUnit,
    hydrate_hits,
    select_context,
)
from mari_components.sync import SyncState, apply_sync_plan, plan_sync
from mari_components.types import ChangeHint, KnowledgeDocument, PollPage, SyncMode

NOW = datetime(2026, 7, 1, tzinfo=UTC)


def test_evidence_must_resolve_inside_visible_exact_material() -> None:
    shown = ArtifactRef(artifact_id="policy", revision="v2", unit_id="returns")
    hidden = ArtifactRef(artifact_id="policy", revision="v2", unit_id="shipping")
    evidence = (
        ArtifactEvidence(ref=shown, quote="14 days", start=8, end=15),
        ArtifactEvidence(ref=hidden, quote="overnight"),
    )
    material = {shown.key: "Returns:14 days", hidden.key: "Ships overnight"}
    report = validate_artifact_evidence(
        evidence,
        resolve_text=lambda ref: material.get(ref.key),
        visible_refs=(shown,),
    )
    assert report.valid == (evidence[0],)
    assert report.issues[0].kind is EvidenceIssueKind.NOT_VISIBLE
    assert not report.accepted


def test_hit_hydration_preserves_rank_misses_and_errors() -> None:
    hits = (("a", 2.0), ("missing", 1.0), ("broken", 0.5))

    def resolve(item_id: str) -> RetrievalUnit | None:
        if item_id == "broken":
            raise RuntimeError("offline")
        if item_id == "missing":
            return None
        return RetrievalUnit(
            ref=ArtifactRef(artifact_id="doc", revision="1", unit_id=item_id),
            text="material",
        )

    result = hydrate_hits(
        hits,
        identity=lambda hit: hit[0],
        score=lambda hit: hit[1],
        resolve=resolve,
    )
    assert tuple(value.rank for value in result) == (1, 2, 3)
    assert result[1].error == "not_found"
    assert result[2].error == "RuntimeError: offline"


def test_context_selection_uses_named_budgets_and_explains_rejection() -> None:
    def item(
        name: str, score: float, tokens: float, *, eligible: bool = True
    ) -> ContextItem:
        return ContextItem(
            unit=RetrievalUnit(
                ref=ArtifactRef(artifact_id="doc", revision="1", unit_id=name),
                text=name,
            ),
            score=score,
            costs={"tokens": tokens, "latency_ms": 1},
            eligible=eligible,
            exclusion_reasons=() if eligible else ("historical",),
        )

    result = select_context(
        (
            item("current", 3, 4),
            item("historical", 2, 2, eligible=False),
            item("large", 1, 8),
        ),
        limits={"tokens": 6, "latency_ms": 2},
    )
    assert tuple(value.unit.ref.unit_id for value in result.items) == ("current",)
    assert result.trace[1].reasons == ("historical",)
    assert result.trace[2].reasons == ("tokens_limit",)


def test_bm25_accepts_analyzer_and_revision_checked_deltas() -> None:
    def analyzer(text: str) -> tuple[str, ...]:
        return (
            ("returns",)
            if "refund" in text.casefold()
            else tuple(text.casefold().split())
        )

    index = BM25Index(
        {"returns": "Refund policy", "shipping": "Shipping policy"},
        analyzer=analyzer,
        revisions={"returns": "1", "shipping": "1"},
    )
    assert index.search("refund", limit=1)[0].document_id == "returns"
    assert index.explain("refund", item_id="returns").contributions[0].term == "returns"
    updated = index.with_deltas(
        (
            IndexDelta(
                item_id="returns",
                operation=IndexOperation.UPSERT,
                text="Refund within fourteen days",
                revision="2",
                expected_revision="1",
            ),
        )
    )
    assert updated.revisions["returns"] == "2"
    with pytest.raises(ValueError, match="revision mismatch"):
        updated.with_deltas(
            (
                IndexDelta(
                    item_id="returns",
                    operation=IndexOperation.DELETE,
                    expected_revision="1",
                ),
            )
        )
    empty = BM25Index({"only": "one"}, revisions={"only": "1"}).with_deltas(
        (
            IndexDelta(
                item_id="only",
                operation=IndexOperation.DELETE,
                expected_revision="1",
            ),
        )
    )
    assert empty.search("one", limit=10) == ()


def test_record_diff_finds_same_identity_changed_content() -> None:
    before = (("parse", "def parse(x): return x"),)
    after = (("parse", "def parse(value): return value"),)
    result = diff_records(
        before,
        after,
        identity=lambda row: row[0],
        fingerprint=lambda row: row[1],
    )
    assert result.modified[0].record_id == "parse"
    assert not result.added_ids


def test_adjacency_and_predecessor_dag_keep_alternative_paths() -> None:
    edges = (("a", "b"), ("a", "c"), ("b", "d"), ("c", "d"))
    outgoing = build_adjacency(edges, endpoints=lambda edge: edge)
    incoming = build_adjacency(edges, endpoints=lambda edge: edge, direction="incoming")
    assert incoming["d"] == ("b", "c")
    result = predecessor_dag(("a",), neighbors=outgoing.__getitem__)
    entry = next(value for value in result.entries if value.node == "d")
    assert entry.predecessors == ("b", "c")
    assert entry.shortest_path_count == 2


def test_blocking_and_cluster_diagnostics_explain_transitive_merge() -> None:
    entities = ("a", "b", "c")
    blocked = explain_candidate_pairs(
        entity_ids=entities,
        blocking_keys=lambda item: (
            {"ab"} if item == "a" else {"ab", "bc"} if item == "b" else {"bc"}
        ),
    )
    assert tuple(pair.shared_keys for pair in blocked) == (("ab",), ("bc",))
    result = cluster_matches(
        entity_ids=entities,
        candidate_pairs=(("a", "b"), ("b", "c"), ("a", "c")),
        score=lambda left, right: 0.2 if (left, right) == ("a", "c") else 0.9,
        threshold=0.8,
    )
    diagnostic = inspect_clusters(result)[0]
    assert diagnostic.weakest_accepted_score == 0.9
    assert diagnostic.rejected_internal_links[0].score == 0.2
    resolved = resolve_relation_evidence(
        (("a", "b"),), resolve=lambda _candidate: ("quote",)
    )
    assert resolved[0].evidence == ("quote",)
    assert not hasattr(resolved[0], "accepted")


def test_assertions_group_time_filter_and_leave_disposition_to_caller() -> None:
    old = Assertion(
        assertion_id="old",
        subject="atlas",
        predicate="database",
        value="sqlite",
        recorded_at=NOW,
        valid_time=TimeInterval(start=datetime(2026, 1, 1, tzinfo=UTC)),
    )
    new = Assertion(
        assertion_id="new",
        subject="atlas",
        predicate="database",
        value="postgres",
        recorded_at=NOW,
        valid_time=TimeInterval(start=NOW),
        supersedes=("old",),
    )
    assert group_assertions((new, old))[0][0] == ("atlas", "database")
    plan = plan_assertion_update(
        old,
        kind=AssertionUpdateKind.SUPERSEDE,
        effective_at=NOW,
        replacement=new,
    )
    assert plan.close_previous_at == NOW
    current = valid_at(NOW, interval=lambda assertion: assertion.valid_time)
    permitted = all_of(current, lambda assertion: assertion.value == "postgres")
    assert permitted(new)
    assert interval_contains(
        close_interval(old.valid_time, NOW), datetime(2026, 6, 1, tzinfo=UTC)
    )


def test_graph_context_metrics_do_not_hide_temporal_error() -> None:
    result = evaluate_graph_context(
        ("project", "postgres", "sqlite"),
        evidence_required=("project", "postgres"),
        temporally_valid=("project", "postgres"),
        edges=(("project", "postgres"), ("project", "sqlite")),
    )
    assert result.evidence_coverage == 1
    assert result.temporal_precision == pytest.approx(2 / 3)
    assert result.connected_fraction == 1


def test_parsed_blocks_are_format_neutral_and_parent_checked() -> None:
    parsed = ParsedDocument(
        artifact_id="thread:1",
        revision="2",
        media_type="application/x-chat",
        blocks=(
            ParsedBlock(block_id="root", kind="message", text="Question"),
            ParsedBlock(
                block_id="reply", kind="message", text="Answer", parent_id="root"
            ),
        ),
    )
    assert parsed.blocks[1].parent_id == "root"
    with pytest.raises(ValueError, match="known blocks"):
        ParsedDocument(
            artifact_id="x",
            revision="1",
            media_type="text/plain",
            blocks=(
                ParsedBlock(
                    block_id="child", kind="text", text="x", parent_id="missing"
                ),
            ),
        )


def test_metadata_lineage_keeps_operation_and_role() -> None:
    edges = {
        "answer": (
            LineageEdge(
                child_id="answer",
                parent_id="passage",
                role="evidence",
                operation="summarize",
            ),
        ),
        "passage": (),
    }
    trace = trace_lineage_edges("answer", parents=edges.__getitem__)
    assert trace.edges[0].role == "evidence"
    assert trace.edges[0].operation == "summarize"


def test_sync_application_checks_generation_through_caller_transaction() -> None:
    document = KnowledgeDocument(
        source_id="notes", external_id="one", title="One", body="Body", revision="1"
    )
    plan = plan_sync(
        SyncState(source_id="notes"),
        PollPage(upserts=(document,), snapshot_complete=True),
        source_id="notes",
        mode=SyncMode.INCREMENTAL,
    )

    class Transaction:
        generation = 0

        def __init__(self) -> None:
            self.documents: dict[str, KnowledgeDocument] = {}
            self.state: SyncState | None = None

        def upsert(self, value: KnowledgeDocument) -> None:
            self.documents[value.document_id] = value

        def delete(self, _value: object) -> None:
            raise AssertionError("unexpected delete")

        def commit(self, state: SyncState) -> None:
            self.state = state

    transaction = Transaction()
    apply_sync_plan(plan, transaction=transaction)
    assert transaction.state == plan.state
    transaction.generation = 2
    with pytest.raises(ValueError, match="generation mismatch"):
        apply_sync_plan(plan, transaction=transaction)


def test_verified_hints_can_be_hydrated_without_stream_checkpointing() -> None:
    hints = (
        ChangeHint(
            provider="custom",
            aggregate_key="space",
            event_type="updated",
            external_id="one",
        ),
    )
    pages = tuple(
        hydrate_hints(
            hints,
            hydrate=lambda hint: (
                PollPage(
                    upserts=(
                        KnowledgeDocument(
                            source_id="notes",
                            external_id=hint.external_id,
                            title="One",
                            body="Body",
                            revision="1",
                        ),
                    ),
                    snapshot_complete=True,
                ),
            ),
        )
    )
    assert pages[0].upserts[0].external_id == "one"
