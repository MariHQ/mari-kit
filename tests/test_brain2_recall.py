"""Behavioral checks for the company-brain filtered-retrieval recall runner.

The tests pin the observable contract of ``benchmarks/company_brain_recall.py``:
recall is always reported with a denominator, authorization allowlists are
never escaped, known-relevant BM25 documents survive edits/deletions
correctly, and incremental ``with_deltas`` snapshots are rebuild-equivalent.
"""

from __future__ import annotations

import copy
import json

import pytest

from benchmarks.company_brain_recall import (
    bm25_lifecycle,
    dense_vectors,
    filtered_dense_recall,
    main,
    run_benchmark,
)
from mari_kit.retrieval import BM25Index, IndexDelta, IndexOperation

TIMING_KEY = "timing_seconds"


def _strip_timing(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: _strip_timing(item) for key, item in value.items() if key != TIMING_KEY
        }
    if isinstance(value, list):
        return [_strip_timing(item) for item in value]
    return copy.deepcopy(value)


def _small_report() -> dict:
    return run_benchmark(
        size=48,
        dimension=16,
        query_count=6,
        k=5,
        seed=7,
        m=4,
        ef_search=32,
        allowlist_sizes=(1, 2, 4, 8),
    )


def test_filtered_recall_reports_denominators_and_never_escapes_allowlist() -> None:
    report = filtered_dense_recall(
        dense_vectors(64, 16, 3),
        seed=3,
        query_count=6,
        k=5,
        allowlist_sizes=(1, 2, 4, 8, 64),
        m=4,
        ef_search=32,
    )
    rows = report["by_allowlist_size"]
    assert [row["allowlist_size"] for row in rows] == [1, 2, 4, 8, 64]
    for row in rows:
        assert row["unauthorized_hits"] == 0
        assert row["queries"] == 6
        assert row["recall_denominator"] == 6 * min(5, row["allowlist_size"])
        assert 0 <= row["recall_numerator"] <= row["recall_denominator"]
        assert row["missed_relevant_hits"] == (
            row["recall_denominator"] - row["recall_numerator"]
        )
    assert report["totals"]["unauthorized_hits"] == 0
    assert report["totals"]["recall_denominator"] == sum(
        row["recall_denominator"] for row in rows
    )
    sweep = report["ef_search_sensitivity"]
    assert {row["allowlist_size"] for row in sweep} == {4, 64}
    assert all(row["unauthorized_hits"] == 0 for row in sweep)


def test_singleton_allowlist_is_exact_for_flat_and_hnsw() -> None:
    report = filtered_dense_recall(
        dense_vectors(40, 12, 11),
        seed=11,
        query_count=5,
        k=5,
        allowlist_sizes=(1,),
        m=4,
        ef_search=32,
    )
    row = report["by_allowlist_size"][0]
    assert row["recall_numerator"] == row["recall_denominator"] == 5


def test_hnsw_filtering_removes_disallowed_neighbors_before_return() -> None:
    report = filtered_dense_recall(
        {"public": [0.0, 1.0], "secret": [1.0, 0.0], "other": [0.7, 0.7]},
        seed=1,
        query_count=1,
        k=3,
        allowlist_sizes=(2,),
        m=2,
        ef_search=16,
    )
    assert report["by_allowlist_size"][0]["unauthorized_hits"] == 0


def test_bm25_lifecycle_tracks_known_relevant_documents_across_changes() -> None:
    report = bm25_lifecycle(24, seed=5, k=5, probe_limit=5)
    before = report["before"]
    after = report["after"]
    assert before["edited_marker"] == ["lex-0000"]
    assert before["deleted_marker"] == ["lex-0001"]
    assert before["edited_new_marker"] == []
    assert after["edited_old_marker"] == []
    assert after["deleted_old_marker"] == []
    assert after["edited_new_marker"] == ["lex-0000"]
    assert after["inserted_marker"] == ["lex-inserted"]
    assert report["deleted_document_visible"] is False
    assert report["recall_before"]["recall_numerator"] == 2
    assert report["recall_before"]["recall_denominator"] == 2
    assert report["recall_before"]["unexpected_positive_hits"] == 0
    assert report["recall_after"]["recall_numerator"] == 2
    assert report["recall_after"]["recall_denominator"] == 2
    assert report["recall_after"]["unexpected_positive_hits"] == 0


def test_bm25_restricted_query_respects_allowlist() -> None:
    report = bm25_lifecycle(24, seed=5, k=5, probe_limit=5)
    restricted = report["restricted_query"]
    assert restricted["positive_hits"] == []
    assert restricted["unauthorized_hits"] == 0


def test_bm25_incremental_snapshot_is_rebuild_equivalent() -> None:
    report = run_benchmark(
        size=32,
        dimension=12,
        query_count=4,
        k=5,
        seed=9,
        m=4,
        ef_search=24,
        allowlist_sizes=(1, 4),
    )
    equivalence = report["lexical_lifecycle"]["rebuild_equivalence"]
    assert equivalence["queries_compared"] > 0
    assert equivalence["documents_equal"] is True
    assert equivalence["revisions_equal"] is True
    assert equivalence["rankings_equal"] is True
    assert equivalence["mismatches"] == []


def test_bm25_with_deltas_checks_revision_and_keeps_base_snapshot() -> None:
    base = BM25Index({"a": "zephyr policy"}, revisions={"a": "1"})
    with pytest.raises(ValueError, match="revision mismatch for 'a'"):
        base.with_deltas(
            (
                IndexDelta(
                    item_id="a",
                    operation=IndexOperation.UPSERT,
                    revision="2",
                    text="quokka",
                    expected_revision="9",
                ),
            )
        )
    assert base.documents == {"a": "zephyr policy"}
    assert base.revisions == {"a": "1"}


def test_run_benchmark_is_deterministic_for_a_fixed_seed() -> None:
    first = _strip_timing(_small_report())
    second = _strip_timing(_small_report())
    assert first == second


def test_cli_writes_json_output(tmp_path) -> None:
    target = tmp_path / "nested" / "recall.json"
    exit_code = main(
        [
            "--size",
            "48",
            "--queries",
            "6",
            "--k",
            "5",
            "--seed",
            "7",
            "--m",
            "4",
            "--ef-search",
            "32",
            "--allowlist-sizes",
            "1",
            "2",
            "4",
            "--output",
            str(target),
        ]
    )
    assert exit_code == 0
    payload = json.loads(target.read_text())
    assert payload["configuration"]["size"] == 48
    assert payload["configuration"]["allowlist_sizes"] == [1, 2, 4]
    assert payload["dense_filtered_recall"]["corpus_size"] == 48
    assert payload["lexical_lifecycle"]["rebuild_equivalence"]["rankings_equal"]


def test_run_benchmark_rejects_tiny_corpus() -> None:
    with pytest.raises(ValueError, match="at least two"):
        run_benchmark(
            size=1,
            dimension=8,
            query_count=1,
            k=1,
            seed=1,
            m=2,
            ef_search=4,
            allowlist_sizes=(1,),
        )
