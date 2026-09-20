"""Independent metric validation for the durable company-brain scale benchmark.

Owned by the scale reviewer. These tests re-derive the numbers reported by
``benchmarks/company_brain_scale.py`` from public inputs and one small,
deterministic end-to-end run. They validate that percentiles, phase sample
counts, authorization counts, query relevance, and index-update equivalence are
functionally meaningful rather than merely present. They never assert latency
thresholds, per the shared contract.
"""

from __future__ import annotations

import math

import pytest

from benchmarks.company_brain_scale import (
    DEFAULT_SEARCH_GROUP,
    DEFAULT_SEARCH_USER,
    DEFAULT_SEED,
    build_documents,
    build_edits,
    build_queries,
    host_allowed_refs,
    latency_summary,
    percentile,
    run,
)
from mari_kit import ScopeRef
from mari_kit.retrieval import (
    IndexOperation,
    RevisionBM25Index,
    RevisionIndexDelta,
)

SCOPE = ScopeRef(tenant="scale", space="company")
SIZE = 40
QUERIES = 8
EDIT_FRACTION = 0.25
DELETE_FRACTION = 0.1

EXPECTED_PHASES = {
    "commit",
    "cold_index_build",
    "acl_filtered_query",
    "batch_edit_commit",
    "batch_edit_index_update",
    "batch_delete_commit",
    "batch_delete_index_update",
}
# The reviewer recommends renaming the prebuilt-index phase away from "warm"
# (the durable engine has no warm query path). Accept either spelling so these
# tests keep validating the metric after that rename.
REFERENCE_QUERY_PHASES = ("warm_lexical_query", "reference_index_query")


def _phase(result, *names):
    for name in names:
        if name in result["phases"]:
            return result["phases"][name]
    raise AssertionError(f"none of {names} present; have {sorted(result['phases'])}")


@pytest.fixture(scope="module")
def scale_run(tmp_path_factory):
    workdir = tmp_path_factory.mktemp("scale-review")
    report = run(
        [SIZE],
        seed=DEFAULT_SEED,
        query_count=QUERIES,
        limit=3,
        edit_fraction=EDIT_FRACTION,
        delete_fraction=DELETE_FRACTION,
        tracemalloc_enabled=False,
        engine_probe=True,
        workdir=workdir,
    )
    return report, report["results"][0]


# --- percentile and latency math --------------------------------------------


def test_nearest_rank_percentile_matches_reference() -> None:
    for size in range(1, 41):
        samples = [float(index) for index in range(1, size + 1)]
        for fraction in (0.0, 0.1, 0.5, 0.9, 0.95, 0.99, 1.0):
            rank = max(1, math.ceil(fraction * size))
            assert percentile(samples, fraction) == samples[rank - 1]


def test_latency_summary_is_consistent_with_samples() -> None:
    samples = [0.004, 0.001, 0.010, 0.002, 0.007]
    summary = latency_summary(samples)
    ordered = sorted(samples)

    assert summary["count"] == len(samples)
    assert summary["total_seconds"] == pytest.approx(sum(samples), abs=1e-9)
    assert summary["mean_seconds"] == pytest.approx(
        sum(samples) / len(samples), abs=1e-9
    )
    assert summary["min_seconds"] == ordered[0]
    assert summary["max_seconds"] == ordered[-1]
    assert (
        summary["min_seconds"]
        <= summary["p50_seconds"]
        <= summary["p95_seconds"]
        <= summary["max_seconds"]
    )


# --- report shape and counting semantics ------------------------------------


def test_report_separates_required_phases(scale_run) -> None:
    _report, result = scale_run

    assert EXPECTED_PHASES <= set(result["phases"])
    assert any(name in result["phases"] for name in REFERENCE_QUERY_PHASES)
    assert result["counts"]["commit_plans"] == len(
        {document.source_id for document in build_documents(SIZE, seed=DEFAULT_SEED)}
    )


def test_phase_sample_counts_match_independently_built_inputs(scale_run) -> None:
    _report, result = scale_run
    phases = result["phases"]
    documents = build_documents(SIZE, seed=DEFAULT_SEED)

    assert (
        _phase(result, *REFERENCE_QUERY_PHASES)["latency"]["count"] == result["queries"]
    )
    assert phases["acl_filtered_query"]["latency"]["count"] == result["queries"]
    assert phases["cold_index_build"]["latency"]["count"] == 1

    edits = build_edits(
        documents, count=result["counts"]["edit_documents"], seed=DEFAULT_SEED
    )
    assert phases["batch_edit_commit"]["latency"]["count"] == len(
        {edit.source_id for edit in edits}
    )
    assert phases["batch_edit_index_update"]["latency"]["count"] == 1


def test_run_counts_and_projection_stay_consistent(scale_run) -> None:
    _report, result = scale_run
    counts = result["counts"]

    assert result["size"] == SIZE
    assert result["documents"] == SIZE
    assert counts["commit_documents"] == SIZE
    assert counts["live_documents"] == SIZE
    assert counts["projection_documents"] == SIZE
    assert counts["cold_index_units"] == SIZE
    assert counts["edit_documents"] == int(SIZE * EDIT_FRACTION)
    assert counts["delete_documents"] == int(SIZE * DELETE_FRACTION)
    assert counts["final_live_documents"] == SIZE - int(SIZE * DELETE_FRACTION)
    assert result["final_projection_documents"] == counts["final_live_documents"]
    assert "consistency_warning" not in result


def test_memory_metrics_are_disclosed_as_process_high_water(scale_run) -> None:
    report, result = scale_run

    assert "high-water" in report["memory_note"]
    for phase in result["phases"].values():
        assert phase["process_rss_before_bytes"] <= phase["process_rss_after_bytes"]
        assert phase["allocations_peak_bytes"] >= 0
    assert result["process_rss_peak_bytes"] >= max(
        phase["process_rss_after_bytes"] for phase in result["phases"].values()
    )


# --- authorization, relevance, and update equivalence -----------------------


def test_authorized_refs_match_independent_policy_evaluation(scale_run) -> None:
    _report, result = scale_run
    documents = build_documents(SIZE, seed=DEFAULT_SEED)
    allowed = host_allowed_refs(
        documents,
        groups={DEFAULT_SEARCH_GROUP},
        user_id=DEFAULT_SEARCH_USER,
        scope=SCOPE,
    )

    assert result["counts"]["authorized_refs"] == len(allowed)
    assert 0 < len(allowed) <= len(documents)
    assert result["counts"]["total_refs"] == len(documents)


def test_benchmark_queries_are_lexically_relevant() -> None:
    documents = build_documents(200, seed=DEFAULT_SEED)
    units = {
        document.ref_in(SCOPE): f"{document.title} {document.body}"
        for document in documents
    }
    index = RevisionBM25Index(units)
    queries = build_queries(20, seed=DEFAULT_SEED)

    positive = sum(
        1
        for query in queries
        if any(hit.score > 0.0 for hit in index.search(query, limit=5))
    )
    assert positive == len(queries)


def _ranking(index: RevisionBM25Index, query: str) -> list[tuple[str, float]]:
    return [(hit.ref.key, round(hit.score, 12)) for hit in index.search(query, limit=5)]


def test_reference_index_delta_update_equals_a_fresh_rebuild() -> None:
    documents = build_documents(60, seed=DEFAULT_SEED)
    units = {
        document.ref_in(SCOPE): f"{document.title} {document.body}"
        for document in documents
    }
    index = RevisionBM25Index(units)
    prior = {document.document_id: document.ref_in(SCOPE) for document in documents}
    edits = build_edits(documents, count=6, seed=DEFAULT_SEED)

    updated = index.with_deltas(
        [
            RevisionIndexDelta(
                ref=edit.ref_in(SCOPE),
                previous_ref=prior[edit.document_id],
                operation=IndexOperation.UPSERT,
                text=f"{edit.title} {edit.body}",
            )
            for edit in edits
        ]
    )

    final = dict(units)
    for edit in edits:
        final.pop(prior[edit.document_id])
        final[edit.ref_in(SCOPE)] = f"{edit.title} {edit.body}"
    fresh = RevisionBM25Index(final)

    for query in build_queries(12, seed=DEFAULT_SEED):
        assert _ranking(updated, query) == _ranking(fresh, query)


def test_engine_probe_exercises_the_real_engine(scale_run) -> None:
    _report, result = scale_run
    engine = result["engine"]

    assert engine["probed"] is True
    assert engine["disposition"] in {"grounded", "insufficient_evidence"}
    assert engine["evidence_count"] >= 0
    assert result["phases"]["engine_search"]["latency"]["count"] >= 1
    assert result["phases"]["engine_answer"]["latency"]["count"] >= 1
    assert result["phases"]["engine_search"]["wall_seconds"] > 0.0
    assert result["phases"]["engine_answer"]["wall_seconds"] > 0.0
