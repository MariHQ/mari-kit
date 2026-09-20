"""Behavioral checks for the opt-in exact fallback in ``HNSWIndex`` search.

The contract under test is narrow and authorization-critical:

* With an explicit allowlist whose effective (known, authorized) size is at or
  below ``exact_filter_threshold``, ``HNSWIndex.search`` must return exactly
  what the exact ``DenseFlatIndex`` returns for that allowlist.
* The default (``exact_filter_threshold=0``) and allowlist-free call paths are
  unchanged.
* Unauthorized vectors are never scored, and unknown IDs never inflate the
  effective allowed count.
* The ``benchmarks/company_brain_filtered_recall.py`` runner reuses the wave-2
  deterministic masks, reports actual recall with denominators, and emits
  timing for the approximate and fallback sweeps.
"""

from __future__ import annotations

import copy
import json

import pytest

from benchmarks.company_brain_filtered_recall import (
    DEFAULT_EXACT_FILTER_THRESHOLD,
    main,
    run_benchmark,
)
from benchmarks.company_brain_recall import dense_vectors, filtered_dense_recall
from mari_kit.retrieval import DenseFlatIndex, HNSWIndex

TIMING_KEY = "timing_seconds"


def _is_timing_key(key: str) -> bool:
    return key == TIMING_KEY or key == "timing_ratio" or key.endswith("_seconds")


def _vectors() -> dict[str, list[float]]:
    return {
        "a": [1.0, 0.0, 0.0],
        "b": [0.0, 1.0, 0.0],
        "c": [0.0, 0.0, 1.0],
        "d": [1.0, 1.0, 0.0],
        "e": [0.5, 0.5, 0.5],
        "f": [-1.0, 0.0, 0.0],
    }


class _FlatRecorder:
    """Wrap a ``DenseFlatIndex`` to observe whether the fallback delegated."""

    def __init__(self, flat: DenseFlatIndex) -> None:
        self._flat = flat
        self.calls: list[set[str]] = []

    def __getattr__(self, name: str) -> object:
        return getattr(self._flat, name)

    def search(self, query, *, limit, allowed_document_ids=None):
        self.calls.append(set(allowed_document_ids or ()))
        return self._flat.search(
            query, limit=limit, allowed_document_ids=allowed_document_ids
        )


def _strip_timing(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: _strip_timing(item)
            for key, item in value.items()
            if not _is_timing_key(key)
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
        exact_filter_threshold=4,
    )


@pytest.mark.parametrize("metric", ["cosine", "dot", "l2"])
def test_exact_fallback_is_bit_identical_to_flat_for_all_metrics(metric: str) -> None:
    vectors = _vectors()
    flat = DenseFlatIndex(vectors, metric=metric)
    hnsw = HNSWIndex(vectors, m=2, metric=metric)
    allowed = {"a", "b", "d"}
    queries = (
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [1.0, 1.0, 0.0],
        [0.2, 0.3, 0.5],
        [-1.0, 2.0, 0.0],
    )
    for query in queries:
        expected = tuple(flat.search(query, limit=3, allowed_document_ids=allowed))
        actual = hnsw.search(
            query,
            limit=3,
            allowed_document_ids=allowed,
            exact_filter_threshold=len(allowed),
        )
        assert actual == expected


def test_fallback_repeats_are_deterministic() -> None:
    flat = DenseFlatIndex(_vectors())
    hnsw = HNSWIndex(_vectors(), m=2)
    allowed = {"a", "c", "e"}
    query = [0.9, 0.1, 0.2]
    reference = tuple(flat.search(query, limit=3, allowed_document_ids=allowed))
    results = {
        hnsw.search(
            query,
            limit=3,
            allowed_document_ids=allowed,
            exact_filter_threshold=5,
        )
        for _ in range(5)
    }
    assert results == {reference}


def test_default_and_explicit_zero_threshold_are_identical() -> None:
    hnsw = HNSWIndex(_vectors(), m=2)
    allowed = {"a", "b", "c"}
    query = [1.0, 0.5, 0.0]
    assert hnsw.search(
        query, limit=2, ef_search=4, allowed_document_ids=allowed
    ) == hnsw.search(
        query,
        limit=2,
        ef_search=4,
        allowed_document_ids=allowed,
        exact_filter_threshold=0,
    )


def test_large_threshold_without_allowlist_stays_on_hnsw_path() -> None:
    hnsw = HNSWIndex(_vectors(), m=2)
    query = [1.0, 0.0, 0.0]
    assert hnsw.search(
        query, limit=2, ef_search=4, exact_filter_threshold=1000
    ) == hnsw.search(query, limit=2, ef_search=4)


def test_fallback_counts_effective_authorized_ids_only() -> None:
    hnsw = HNSWIndex(_vectors(), m=2)
    recorder = _FlatRecorder(hnsw.flat)
    hnsw.flat = recorder
    padded = {"a", "ghost-0", "ghost-1", "ghost-2"}
    hnsw.search(
        [1.0, 0.0, 0.0],
        limit=1,
        allowed_document_ids=padded,
        exact_filter_threshold=1,
    )
    assert recorder.calls == [{"a"}]

    recorder.calls.clear()
    hnsw.search(
        [1.0, 0.0, 0.0],
        limit=1,
        allowed_document_ids={"a", "b"},
        exact_filter_threshold=1,
    )
    assert recorder.calls == []

    recorder.calls.clear()
    hnsw.search(
        [1.0, 0.0, 0.0],
        limit=2,
        allowed_document_ids=padded,
        exact_filter_threshold=0,
    )
    assert recorder.calls == []


def test_fallback_never_returns_or_scores_unauthorized_ids() -> None:
    vectors = _vectors()
    flat = DenseFlatIndex(vectors)
    hnsw = HNSWIndex(vectors, m=2)
    allowed = {"a", "e"}
    query = [1.0, 0.0, 0.0]
    hits = hnsw.search(
        query,
        limit=5,
        allowed_document_ids=allowed | {"ghost"},
        exact_filter_threshold=2,
    )
    assert {hit.document_id for hit in hits} <= allowed
    assert hits == tuple(flat.search(query, limit=5, allowed_document_ids=allowed))


def test_unknown_and_empty_allowlists_return_no_hits() -> None:
    hnsw = HNSWIndex(_vectors(), m=2)
    assert (
        hnsw.search(
            [1.0, 0.0, 0.0],
            limit=3,
            allowed_document_ids={"ghost"},
            exact_filter_threshold=5,
        )
        == ()
    )
    assert (
        hnsw.search(
            [1.0, 0.0, 0.0],
            limit=3,
            allowed_document_ids=set(),
            exact_filter_threshold=5,
        )
        == ()
    )


def test_fallback_respects_limit_and_tie_break_order() -> None:
    vectors = {"x": [1.0, 0.0], "y": [0.5, 0.0], "z": [0.5, 0.0]}
    flat = DenseFlatIndex(vectors)
    hnsw = HNSWIndex(vectors, m=2)
    allowed = {"x", "y", "z"}
    for limit in range(0, 4):
        assert hnsw.search(
            [1.0, 0.0],
            limit=limit,
            allowed_document_ids=allowed,
            exact_filter_threshold=3,
        ) == tuple(flat.search([1.0, 0.0], limit=limit, allowed_document_ids=allowed))


def test_invalid_exact_filter_threshold_is_rejected() -> None:
    hnsw = HNSWIndex(_vectors(), m=2)
    query = [1.0, 0.0, 0.0]
    for bad in (-1, 1.5, True, "2", None):
        with pytest.raises(ValueError, match="non-negative integer"):
            hnsw.search(
                query,
                limit=1,
                ef_search=1,
                exact_filter_threshold=bad,
            )


def test_fallback_recall_is_exact_and_reports_timing() -> None:
    data = _small_report()["filtered_fallback_recall"]
    assert data["exact_filter_threshold"] == 4
    assert data["queries"] == 6
    for row in data["by_allowlist_size"]:
        size = row["allowlist_size"]
        approximate = row["approximate"]
        fallback = row["fallback"]
        assert approximate["unauthorized_hits"] == 0
        assert fallback["unauthorized_hits"] == 0
        assert row["fallback_engaged"] is (size <= 4)
        assert approximate["recall_denominator"] == 6 * min(5, size)
        assert fallback["recall_denominator"] == approximate["recall_denominator"]
        if row["fallback_engaged"]:
            assert fallback["recall"] == 1.0
            assert fallback["recall_numerator"] == fallback["recall_denominator"]
            assert fallback["missed_relevant_hits"] == 0
        else:
            assert fallback["recall"] == approximate["recall"]
            assert fallback["recall_numerator"] == approximate["recall_numerator"]
        assert fallback["recall"] >= approximate["recall"]
        assert fallback["timing_seconds"]["search"] >= 0.0
        assert approximate["timing_seconds"]["search"] >= 0.0
    totals = data["totals"]
    assert (
        totals["recall_gain"]
        == totals["fallback"]["recall"] - totals["approximate"]["recall"]
    )
    assert totals["unauthorized_hits"] == 0


def test_benchmark_approximate_masks_match_wave2_helpers() -> None:
    vectors = dense_vectors(48, 16, 7)
    wave2 = filtered_dense_recall(
        vectors,
        seed=7,
        query_count=6,
        k=5,
        allowlist_sizes=(1, 2, 4, 8),
        m=4,
        ef_search=32,
    )
    mine = run_benchmark(
        size=48,
        dimension=16,
        query_count=6,
        k=5,
        seed=7,
        m=4,
        ef_search=32,
        allowlist_sizes=(1, 2, 4, 8),
        exact_filter_threshold=4,
    )["filtered_fallback_recall"]
    assert [row["allowlist_size"] for row in wave2["by_allowlist_size"]] == [
        row["allowlist_size"] for row in mine["by_allowlist_size"]
    ]
    for wave_row, row in zip(
        wave2["by_allowlist_size"], mine["by_allowlist_size"], strict=True
    ):
        approximate = row["approximate"]
        assert wave_row["recall_numerator"] == approximate["recall_numerator"]
        assert wave_row["recall_denominator"] == approximate["recall_denominator"]
        assert wave_row["unauthorized_hits"] == approximate["unauthorized_hits"]
    assert (
        wave2["totals"]["recall_numerator"]
        == mine["totals"]["approximate"]["recall_numerator"]
    )
    assert (
        wave2["totals"]["recall_denominator"]
        == mine["totals"]["approximate"]["recall_denominator"]
    )


def test_run_benchmark_is_deterministic_when_timing_is_stripped() -> None:
    assert _strip_timing(_small_report()) == _strip_timing(_small_report())


def test_run_benchmark_rejects_tiny_corpus_and_invalid_threshold() -> None:
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
    for bad in (-1, 2.5, True):
        with pytest.raises(ValueError, match="non-negative integer"):
            run_benchmark(
                size=16,
                dimension=8,
                query_count=2,
                k=2,
                seed=1,
                m=2,
                ef_search=4,
                allowlist_sizes=(1,),
                exact_filter_threshold=bad,
            )


def test_cli_writes_json_output(tmp_path) -> None:
    target = tmp_path / "nested" / "fallback.json"
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
            "--exact-filter-threshold",
            "4",
            "--output",
            str(target),
        ]
    )
    assert exit_code == 0
    payload = json.loads(target.read_text())
    assert payload["configuration"]["size"] == 48
    assert payload["configuration"]["allowlist_sizes"] == [1, 2, 4]
    assert payload["configuration"]["exact_filter_threshold"] == 4
    data = payload["filtered_fallback_recall"]
    assert data["totals"]["fallback"]["unauthorized_hits"] == 0
    assert data["totals"]["approximate"]["unauthorized_hits"] == 0


def test_default_threshold_constant_is_opt_in_and_small() -> None:
    assert isinstance(DEFAULT_EXACT_FILTER_THRESHOLD, int)
    assert DEFAULT_EXACT_FILTER_THRESHOLD > 0
