from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from mari_components.connectors import coalesce_hints_ordered
from mari_components.evaluation import evaluate_grouped_coverage
from mari_components.graph import (
    TimeInterval,
    diff_record_fields,
    grouped_interval_overlaps,
    project_graph_evidence,
    traverse_edges,
)
from mari_components.json import to_json_value
from mari_components.knowledge import (
    ArtifactRef,
    WeightedObservation,
    resolve_version_families,
    weighted_mean,
    wilson_proportion,
)
from mari_components.retrieval import (
    ArtifactBM25Index,
    ArtifactIndexDelta,
    CandidateDecision,
    CandidateHistory,
    ContextItem,
    FilterPredicate,
    IndexOperation,
    RetrievalUnit,
    decisions_from_context,
    decisions_from_filter,
    diagnose_candidate_history,
    filter_with_reasons,
    select_context_diverse,
)
from mari_components.types import ChangeHint


def context_item(
    item_id: str, score: float, *, group: str, tokens: float = 1
) -> ContextItem:
    return ContextItem(
        unit=RetrievalUnit(
            ref=ArtifactRef(artifact_id=item_id, revision="1"),
            text=item_id,
            metadata={"group": group},
        ),
        score=score,
        costs={"items": 1, "tokens": tokens},
    )


def test_filters_and_candidate_history_preserve_upstream_attrition() -> None:
    result = filter_with_reasons(
        ("current-ca", "expired-ca", "current-eu"),
        predicates=(
            FilterPredicate(
                reason="expired", accepts=lambda item: "expired" not in item
            ),
            FilterPredicate(
                reason="wrong_scope", accepts=lambda item: "eu" not in item
            ),
        ),
    )
    assert result.accepted == ("current-ca",)
    assert result.decisions[1].reasons == ("expired",)
    assert result.decisions[2].reasons == ("wrong_scope",)
    history = CandidateHistory().append(
        CandidateDecision(
            candidate_id="successful-outcome",
            stage="graph_selection",
            included=False,
            reasons=("node_limit",),
            scores={"outcome": 1.0},
        ),
        CandidateDecision(
            candidate_id="failed-outcome",
            stage="context_selection",
            included=True,
            parent_ids=("restart-node",),
        ),
    )
    assert history.for_candidate("successful-outcome")[0].reasons == ("node_limit",)
    converted = decisions_from_filter(
        result, stage="eligibility", identity=lambda item: item
    )
    assert converted[1].reasons == ("expired",)


def test_candidate_history_diagnostics_use_caller_identity_normalization() -> None:
    ref = ArtifactRef(artifact_id="clause", revision="2")
    history = CandidateHistory(
        decisions=(
            CandidateDecision(
                candidate_id="clause@2", stage="rank", included=True
            ),
            CandidateDecision(
                candidate_id=ref,
                stage="rank",
                included=False,
                reasons=("stale",),
                parent_ids=("source:missing",),
            ),
        )
    )
    diagnostics = diagnose_candidate_history(
        history,
        canonicalize=lambda value: (
            value.artifact_id if isinstance(value, ArtifactRef) else value.split("@")[0]
        ),
    )
    assert diagnostics.identity_aliases == (("clause@2", ref),)
    assert diagnostics.conflicting_stage_decisions == (("clause", "rank"),)
    assert diagnostics.missing_parent_ids == ("source:missing",)


def test_diverse_selection_prevents_one_version_family_consuming_budget() -> None:
    items = (
        context_item("preprint", 3.0, group="trial-b"),
        context_item("journal", 2.9, group="trial-b"),
        context_item("contradiction", 2.0, group="trial-c"),
    )
    selected = select_context_diverse(
        items,
        limits={"items": 2, "tokens": 2},
        groups=lambda item: (item.unit.metadata["group"],),
        maximum_per_group={"trial-b": 1, "trial-c": 1},
        minimum_per_group={"trial-b": 1, "trial-c": 1},
    )
    assert tuple(item.unit.ref.artifact_id for item in selected.items) == (
        "preprint",
        "contradiction",
    )
    duplicate = next(
        trace for trace in selected.trace if trace.ref.artifact_id == "journal"
    )
    assert "group_limit:'trial-b'" in duplicate.reasons
    assert duplicate.marginal_gain == 2.9
    assert selected.unsatisfied_groups == ()
    assert tuple(
        round_.selected_ref.artifact_id
        for round_ in selected.rounds
        if round_.selected_ref is not None
    ) == (
        "preprint",
        "contradiction",
    )
    second_round_duplicate = next(
        candidate
        for candidate in selected.rounds[1].candidates
        if candidate.ref.artifact_id == "journal"
    )
    assert second_round_duplicate.reasons == ("group_limit:'trial-b'",)
    assert selected.rounds[-1].stop_reason == "no_feasible_candidate"
    decisions = decisions_from_context(selected, stage="context")
    assert decisions[1].scores["marginal_gain"] == 2.9


def test_graph_evidence_projection_retains_many_to_many_reasons() -> None:
    topology = ArtifactRef(artifact_id="topology", revision="4")
    runbook = ArtifactRef(artifact_id="runbook", revision="2")
    mapping = {"api": (topology, runbook), "db": (topology,), "unknown": ()}
    result = project_graph_evidence(
        ("api", "db", "unknown"),
        artifacts=mapping.__getitem__,
        score=lambda node: {"api": 3, "db": 2, "unknown": 0}[node],
        path=lambda node: ("alert", node),
    )
    assert len(result.associations) == 3
    assert result.artifact_refs == (runbook, topology)
    assert result.missing_nodes == ("unknown",)


@dataclass(frozen=True)
class Clause:
    clause_id: str
    scope: str
    text: str
    interval: TimeInterval


def test_grouped_overlap_sweep_emits_unique_nonself_pairs() -> None:
    jan = datetime(2026, 1, 1, tzinfo=UTC)
    feb = datetime(2026, 2, 1, tzinfo=UTC)
    mar = datetime(2026, 3, 1, tzinfo=UTC)
    clauses = (
        Clause("a", "ca", "one", TimeInterval(start=jan, end=mar)),
        Clause("b", "ca", "two", TimeInterval(start=feb)),
        Clause("c", "eu", "three", TimeInterval(start=jan)),
    )
    overlaps = grouped_interval_overlaps(
        clauses, group=lambda item: item.scope, interval=lambda item: item.interval
    )
    assert tuple((pair.left.clause_id, pair.right.clause_id) for pair in overlaps) == (
        ("a", "b"),
    )
    assert overlaps[0].overlap == TimeInterval(start=feb, end=mar)


def test_field_diff_names_changed_fields() -> None:
    before = (Clause("a", "ca", "two years", TimeInterval()),)
    after = (Clause("a", "ca", "three years", TimeInterval()),)
    changes = diff_record_fields(
        before,
        after,
        identity=lambda item: item.clause_id,
        fields={"scope": lambda item: item.scope, "text": lambda item: item.text},
    )
    assert tuple((change.field, change.before, change.after) for change in changes) == (
        ("text", "two years", "three years"),
    )


@dataclass(frozen=True)
class Citation:
    source: str
    target: str
    retracted: bool = False


def test_edge_traversal_keeps_metadata_and_rejections() -> None:
    citations = {
        "review": (
            Citation("review", "trial"),
            Citation("review", "retracted", retracted=True),
        ),
        "trial": (),
    }
    result = traverse_edges(
        ("review",),
        edges=lambda node: citations.get(node, ()),
        adjacent=lambda _node, edge: edge.target,
        reject_edge=lambda edge: "retracted" if edge.retracted else None,
    )
    assert tuple(visit.node for visit in result.visits) == ("review", "trial")
    assert result.traversed_edges[0].target == "trial"
    assert result.rejected_edges[0].reason == "retracted"


def test_edge_traversal_reports_edges_hidden_by_depth_limit() -> None:
    citations = {
        "review": (Citation("review", "trial"),),
        "trial": (Citation("trial", "appendix"),),
    }
    result = traverse_edges(
        ("review",),
        edges=lambda node: citations.get(node, ()),
        adjacent=lambda _node, edge: edge.target,
        max_depth=1,
    )
    assert result.truncated
    assert len(result.rejected_edges) == 1
    assert result.rejected_edges[0].edge.target == "appendix"
    assert result.rejected_edges[0].reason == "depth_limit"


def test_weighted_aggregation_and_uncertainty_retain_contributions() -> None:
    result = weighted_mean(
        (
            WeightedObservation(
                observation_id="a", value=0.2, weight=2, group="study-a"
            ),
            WeightedObservation(
                observation_id="b", value=-0.1, weight=1, group="study-b"
            ),
        )
    )
    assert result.value == pytest.approx(0.1)
    assert sum(value.contribution for value in result.contributions) == pytest.approx(
        result.value
    )
    interval = wilson_proportion(7, 10)
    assert interval.lower < interval.value < interval.upper
    assert interval.level == pytest.approx(0.95)


def test_grouped_coverage_exposes_duplicate_family_redundancy() -> None:
    family = {"preprint": "trial-b", "journal": "trial-b", "other": "trial-c"}
    result = evaluate_grouped_coverage(
        ("preprint", "journal"),
        ("preprint", "other"),
        group=family.__getitem__,
    )
    assert result.represented_group_fraction == 0.5
    assert result.redundancy_rate == 0.5


def test_artifact_bm25_returns_typed_revision_identity() -> None:
    old = ArtifactRef(artifact_id="clause", revision="1")
    current = ArtifactRef(artifact_id="clause", revision="2")
    index = ArtifactBM25Index(
        {old: "expired retention two years", current: "current retention three years"}
    )
    hits = index.search("current retention", limit=2, allowed_refs=(current,))
    assert hits[0].ref is current
    assert index.explain("current retention", ref=current).ref is current


def test_artifact_bm25_applies_exact_revision_deltas_immutably() -> None:
    old = ArtifactRef(artifact_id="runbook", revision="1")
    current = ArtifactRef(artifact_id="runbook", revision="2")
    original = ArtifactBM25Index({old: "restart service"})
    updated = original.with_deltas(
        (
            ArtifactIndexDelta(
                ref=current,
                previous_ref=old,
                operation=IndexOperation.UPSERT,
                text="shed retries",
            ),
        )
    )
    assert original.search("restart", limit=1)[0].ref == old
    assert updated.search("retries", limit=1)[0].ref == current
    with pytest.raises(ValueError, match="expected artifact revision is absent"):
        updated.with_deltas(
            (
                ArtifactIndexDelta(
                    ref=ArtifactRef(artifact_id="runbook", revision="3"),
                    previous_ref=old,
                    operation=IndexOperation.UPSERT,
                    text="drain queue",
                ),
            )
        )


def test_json_encoding_supports_immutable_mappings() -> None:
    hint = ChangeHint(
        provider="custom",
        aggregate_key="space",
        event_type="updated",
        metadata={"attempt": 2},
    )
    encoded = to_json_value(hint)
    assert json.loads(json.dumps(encoded))["metadata"] == {"attempt": 2}


def test_hint_coalescing_uses_caller_order_and_reports_conflicts() -> None:
    newer = ChangeHint(
        provider="custom",
        aggregate_key="one",
        event_type="updated",
        revision="2",
    )
    older = ChangeHint(
        provider="custom",
        aggregate_key="one",
        event_type="updated",
        revision="1",
    )
    tied = ChangeHint(
        provider="custom",
        aggregate_key="one",
        event_type="deleted",
        revision="2",
        deleted=True,
    )
    report = coalesce_hints_ordered(
        (newer, older, tied), order_key=lambda hint: int(hint.revision)
    )
    assert report.selected == ()
    assert report.stale == (older,)
    assert report.conflicts == ((newer, tied),)
    assert report.unresolved_keys == (("custom", "one"),)


def test_version_family_proposal_exposes_tied_representatives() -> None:
    records = (
        ("preprint", "trial-b", 2),
        ("journal", "trial-b", 3),
        ("correction", "trial-b", 3),
    )
    families = resolve_version_families(
        records, family=lambda row: row[1], score=lambda row: row[2]
    )
    assert families[0].representative == ("correction", "trial-b", 3)
    assert len(families[0].tied_representatives) == 2
