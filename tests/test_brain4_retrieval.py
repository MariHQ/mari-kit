"""Behavioral checks for opt-in deterministic multi-start HNSW search.

Contract under test:

* ``search_starts`` defaults to ``1`` and reproduces the legacy single-start
  traversal exactly; only positive ``int`` values (not ``bool``) are accepted.
* Additional starts are chosen deterministically from authorized IDs only and
  each traversal is bounded by ``ef_search``; the merged candidate set grows
  with ``search_starts``, so top-k scores and exact-recall coverage are
  monotonically non-decreasing.
* Empty/unknown allowlists still return no hits, and unauthorized vectors are
  never scored or returned for ``cosine``, ``dot``, and ``l2``.
* The opt-in exact fallback for small allowlists is unchanged.
* ``benchmarks/company_brain_multistart.py`` reuses the wave-3 corpus, query
  vectors, and allowlist masks and reports recall, latency, and zero
  unauthorized hits.
"""

from __future__ import annotations

import copy
import inspect
import json

import pytest

from benchmarks.company_brain_filtered_recall import _sampled_allowlist
from benchmarks.company_brain_multistart import (
    DEFAULT_ALLOWLIST_SIZES,
    DEFAULT_EXACT_FILTER_THRESHOLD,
    DEFAULT_SEARCH_STARTS,
    DEFAULT_SEED,
    DEFAULT_SIZE,
    WAVE3_QUERIES,
    main,
    run_benchmark,
)
from benchmarks.company_brain_recall import _query_vectors, dense_vectors
from mari_kit.retrieval import DenseFlatIndex, HNSWIndex

METRICS = ("cosine", "dot", "l2")
TIMING_KEY = "timing_seconds"
SMALL = {
    "size": 120,
    "dimension": 12,
    "query_count": 8,
    "k": 8,
    "seed": DEFAULT_SEED,
    "m": 6,
    "ef_search": 12,
}


def _vectors() -> dict[str, list[float]]:
    return {
        "a": [1.0, 0.0, 0.0],
        "b": [0.0, 1.0, 0.0],
        "c": [0.0, 0.0, 1.0],
        "d": [1.0, 1.0, 0.0],
        "e": [0.5, 0.5, 0.5],
        "f": [-1.0, 0.0, 0.0],
    }


def _corpus(size: int = 120, dimension: int = 12) -> dict[str, list[float]]:
    return dense_vectors(size, dimension, DEFAULT_SEED)


def _queries(vectors: dict[str, list[float]], *, count: int = 8) -> list[list[float]]:
    dimension = len(next(iter(vectors.values())))
    return _query_vectors(vectors, count=count, dimension=dimension, seed=DEFAULT_SEED)


def _allowlist(all_ids: list[str], size: int, *, position: int = 0) -> set[str]:
    return _sampled_allowlist(
        all_ids, seed=DEFAULT_SEED, allowlist_size=size, position=position
    )


def _scores(
    hnsw: HNSWIndex,
    query: list[float],
    allowed: set[str],
    *,
    starts: int,
    k: int = 8,
    ef_search: int = 12,
) -> list[float]:
    return [
        hit.score
        for hit in hnsw.search(
            query,
            limit=k,
            ef_search=ef_search,
            allowed_document_ids=allowed,
            search_starts=starts,
        )
    ]


def _padded(scores: list[float], k: int) -> list[float]:
    return [*scores, *[float("-inf")] * (k - len(scores))]


def _recall_tuple(
    exact: DenseFlatIndex,
    hnsw: HNSWIndex,
    query: list[float],
    allowed: set[str],
    *,
    starts: int,
    k: int = 8,
    ef_search: int = 12,
) -> tuple[int, int, set[str]]:
    exact_ids = {
        hit.document_id
        for hit in exact.search(query, limit=k, allowed_document_ids=allowed)
    }
    hit_ids = {
        hit.document_id
        for hit in hnsw.search(
            query,
            limit=k,
            ef_search=ef_search,
            allowed_document_ids=allowed,
            search_starts=starts,
        )
    }
    return len(exact_ids & hit_ids), len(exact_ids), hit_ids


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


def _is_timing_key(key: str) -> bool:
    return (
        key == TIMING_KEY
        or key.endswith("_seconds")
        or key.endswith("_ms")
        or key.endswith("_vs_single")
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


# --- contract: option shape and validation -----------------------------------


def test_search_starts_defaults_to_one_and_constructor_is_unchanged() -> None:
    parameters = inspect.signature(HNSWIndex.search).parameters
    assert "search_starts" in parameters
    default = parameters["search_starts"].default
    assert default == 1
    assert isinstance(default, int)
    assert not isinstance(default, bool)
    assert "search_starts" not in inspect.signature(HNSWIndex.__init__).parameters


def test_invalid_search_starts_are_rejected() -> None:
    hnsw = HNSWIndex(_vectors(), m=2)
    query = [1.0, 0.0, 0.0]
    for bad in (0, -1, True, 1.5, "2", None):
        with pytest.raises(ValueError, match="positive integer"):
            hnsw.search(query, limit=1, ef_search=1, search_starts=bad)


def test_start_selection_does_not_rescan_levels_quadratically() -> None:
    class CountingLevels(dict):
        reads = 0

        def __getitem__(self, key):
            self.reads += 1
            return super().__getitem__(key)

    index = HNSWIndex({str(i): [float(i + 1), 1.0] for i in range(100)}, m=2)
    levels = CountingLevels(index.levels)
    index.levels = levels
    index.search([1.0, 1.0], limit=3)
    assert levels.reads < 1000
    index.search([1.0, 1.0], limit=3, search_starts=4)
    assert levels.reads < 2000


def test_search_starts_beyond_authorized_count_is_capped() -> None:
    hnsw = HNSWIndex(_vectors(), m=2)
    allowed = {"a", "b"}
    hits = hnsw.search(
        [1.0, 0.0, 0.0],
        limit=5,
        ef_search=5,
        allowed_document_ids=allowed,
        search_starts=8,
    )
    assert {hit.document_id for hit in hits} <= allowed
    assert len(hits) <= len(allowed)


# --- default equivalence -----------------------------------------------------


@pytest.mark.parametrize("metric", METRICS)
def test_explicit_single_start_matches_default_everywhere(metric: str) -> None:
    hnsw = HNSWIndex(_vectors(), m=2, metric=metric)
    query = [0.9, 0.1, 0.3]
    for allowed in (None, {"a", "b", "d"}, {"a", "c"}, set(), {"ghost"}):
        default = hnsw.search(query, limit=3, ef_search=5, allowed_document_ids=allowed)
        explicit = hnsw.search(
            query,
            limit=3,
            ef_search=5,
            allowed_document_ids=allowed,
            search_starts=1,
        )
        assert default == explicit


# --- multi-start coverage and scoring ----------------------------------------


@pytest.mark.parametrize("metric", METRICS)
def test_multi_start_scores_and_recall_are_monotonic(metric: str) -> None:
    vectors = _corpus()
    all_ids = sorted(vectors)
    exact = DenseFlatIndex(vectors, metric=metric)
    hnsw = HNSWIndex(vectors, m=6, metric=metric)
    for position, query in enumerate(_queries(vectors)):
        allowed = _allowlist(all_ids, 60, position=position)
        single = _padded(_scores(hnsw, query, allowed, starts=1), 8)
        four = _padded(_scores(hnsw, query, allowed, starts=4), 8)
        eight = _padded(_scores(hnsw, query, allowed, starts=8), 8)
        assert all(
            four_score >= one for one, four_score in zip(single, four, strict=True)
        )
        assert all(
            eight_score >= four_score
            for four_score, eight_score in zip(four, eight, strict=True)
        )
        one_hits = _recall_tuple(exact, hnsw, query, allowed, starts=1)
        four_hits = _recall_tuple(exact, hnsw, query, allowed, starts=4)
        eight_hits = _recall_tuple(exact, hnsw, query, allowed, starts=8)
        assert four_hits[0] >= one_hits[0]
        assert eight_hits[0] >= four_hits[0]
        assert one_hits[1] == four_hits[1] == eight_hits[1]
        assert four_hits[2] <= allowed
        assert eight_hits[2] <= allowed


@pytest.mark.parametrize("metric", METRICS)
def test_multi_start_strictly_improves_larger_allowlist_recall(metric: str) -> None:
    vectors = _corpus()
    all_ids = sorted(vectors)
    exact = DenseFlatIndex(vectors, metric=metric)
    hnsw = HNSWIndex(vectors, m=6, metric=metric)
    totals = {starts: [0, 0] for starts in (1, 4, 8)}
    for position, query in enumerate(_queries(vectors)):
        allowed = _allowlist(all_ids, 60, position=position)
        for starts in totals:
            numerator, denominator, _ = _recall_tuple(
                exact, hnsw, query, allowed, starts=starts
            )
            totals[starts][0] += numerator
            totals[starts][1] += denominator
    single = totals[1][0] / totals[1][1]
    four = totals[4][0] / totals[4][1]
    eight = totals[8][0] / totals[8][1]
    assert four >= single
    assert eight >= four
    assert eight > single


@pytest.mark.parametrize("metric", METRICS)
def test_multi_start_repeats_are_deterministic(metric: str) -> None:
    vectors = _corpus()
    all_ids = sorted(vectors)
    hnsw = HNSWIndex(vectors, m=6, metric=metric)
    query = _queries(vectors)[0]
    allowed = _allowlist(all_ids, 60)
    reference = hnsw.search(
        query,
        limit=8,
        ef_search=12,
        allowed_document_ids=allowed,
        search_starts=4,
    )
    for _ in range(4):
        assert (
            hnsw.search(
                query,
                limit=8,
                ef_search=12,
                allowed_document_ids=allowed,
                search_starts=4,
            )
            == reference
        )


def test_returned_count_respects_limit_and_zero_limit() -> None:
    hnsw = HNSWIndex(_vectors(), m=2)
    allowed = {"a", "b", "c"}
    query = [1.0, 0.5, 0.0]
    for limit in range(0, 5):
        hits = hnsw.search(
            query,
            limit=limit,
            ef_search=5,
            allowed_document_ids=allowed,
            search_starts=4,
        )
        assert len(hits) <= min(limit, len(allowed))
    assert (
        hnsw.search(
            query,
            limit=0,
            ef_search=5,
            allowed_document_ids=allowed,
            search_starts=4,
        )
        == ()
    )


# --- authorization guarantees ------------------------------------------------


def test_start_order_is_deterministic_and_authorized() -> None:
    vectors = _corpus(size=40, dimension=8)
    hnsw = HNSWIndex(vectors, m=4)
    all_ids = sorted(vectors)
    allowed = _allowlist(all_ids, 20)
    order = hnsw._start_order(allowed, len(allowed))
    assert order == hnsw._start_order(allowed, len(allowed))
    assert set(order) <= allowed
    assert len(order) == len(allowed)
    top_level = max(hnsw.levels[identifier] for identifier in allowed)
    assert order[0] == min(
        identifier for identifier in allowed if hnsw.levels[identifier] == top_level
    )


def test_traversal_only_scores_authorized_nodes() -> None:
    hnsw = HNSWIndex(_vectors(), m=2, metric="dot")
    positions = {identifier: index for index, identifier in enumerate(hnsw.flat.ids)}
    allowed = {"a", "b"}
    value = hnsw.flat.vectors[positions["a"]]
    for start in hnsw._start_order(allowed, len(allowed)):
        scored = hnsw._traverse(
            value,
            allowed=allowed,
            positions=positions,
            start=start,
            ef_search=4,
        )
        assert set(scored) <= allowed


@pytest.mark.parametrize("metric", METRICS)
def test_multi_start_never_returns_unauthorized_ids(metric: str) -> None:
    vectors = _corpus()
    all_ids = sorted(vectors)
    hnsw = HNSWIndex(vectors, m=6, metric=metric)
    for position, query in enumerate(_queries(vectors)):
        allowed = _allowlist(all_ids, 30, position=position)
        for starts in (1, 4, 8):
            hit_ids = {
                hit.document_id
                for hit in hnsw.search(
                    query,
                    limit=8,
                    ef_search=12,
                    allowed_document_ids=allowed,
                    search_starts=starts,
                )
            }
            assert hit_ids <= allowed
            assert not hit_ids & (set(all_ids) - allowed)


def test_unknown_and_empty_allowlists_return_no_hits() -> None:
    vectors = _corpus(size=40, dimension=8)
    hnsw = HNSWIndex(vectors, m=4)
    query = [0.5] * 8
    for allowed in (set(), {"ghost-0", "ghost-1"}):
        for starts in (1, 4, 8):
            assert (
                hnsw.search(
                    query,
                    limit=5,
                    ef_search=8,
                    allowed_document_ids=allowed,
                    search_starts=starts,
                )
                == ()
            )
    all_ids = sorted(vectors)
    present = all_ids[0]
    hits = hnsw.search(
        query,
        limit=5,
        ef_search=8,
        allowed_document_ids={present, "ghost-0"},
        search_starts=8,
    )
    assert {hit.document_id for hit in hits} <= {present}


# --- exact fallback is retained ----------------------------------------------


def test_multi_start_retains_exact_filter_fallback() -> None:
    vectors = _corpus(size=40, dimension=8)
    flat = DenseFlatIndex(vectors)
    hnsw = HNSWIndex(vectors, m=4)
    recorder = _FlatRecorder(hnsw.flat)
    hnsw.flat = recorder
    allowed = _allowlist(sorted(vectors), 4)
    query = _queries(vectors)[0]
    expected = tuple(flat.search(query, limit=5, allowed_document_ids=allowed))
    for starts in (1, 4, 8):
        recorder.calls.clear()
        hits = hnsw.search(
            query,
            limit=5,
            ef_search=8,
            allowed_document_ids=allowed,
            exact_filter_threshold=4,
            search_starts=starts,
        )
        assert hits == expected
        assert recorder.calls == [set(allowed)]


# --- benchmark runner --------------------------------------------------------


def _small_report(**overrides) -> dict:
    arguments = {
        **SMALL,
        "allowlist_sizes": (60, 120),
        "search_starts": (1, 4, 8),
        "exact_filter_threshold": 0,
    }
    arguments.update(overrides)
    return run_benchmark(**arguments)


def test_wave3_configuration_defaults_are_recorded() -> None:
    assert DEFAULT_SIZE == 1000
    assert WAVE3_QUERIES == 20
    assert DEFAULT_SEED == 20240919
    assert DEFAULT_ALLOWLIST_SIZES == (200, 1000)
    assert DEFAULT_SEARCH_STARTS == (1, 4, 8)
    assert DEFAULT_EXACT_FILTER_THRESHOLD == 0


def test_benchmark_reports_recall_latency_and_zero_unauthorized() -> None:
    data = _small_report()["multistart_recall"]
    assert data["corpus_size"] == SMALL["size"]
    assert data["queries"] == SMALL["query_count"]
    assert data["totals"]["unauthorized_hits"] == 0
    assert data["totals"]["recall_monotonic_in_starts"] is True
    assert [row["allowlist_size"] for row in data["by_allowlist_size"]] == [60, 120]
    strict_gain = False
    for row in data["by_allowlist_size"]:
        assert row["recall_monotonic_in_starts"] is True
        runs = row["runs"]
        assert [run["search_starts"] for run in runs] == [1, 4, 8]
        expected_denominator = SMALL["query_count"] * min(
            SMALL["k"], row["allowlist_size"]
        )
        for run in runs:
            assert run["recall_denominator"] == expected_denominator
            assert run["recall"] == run["recall_numerator"] / run["recall_denominator"]
            assert run["unauthorized_hits"] == 0
            assert run["timing_seconds"]["search"] >= 0.0
            assert run["timing_seconds"]["per_query"] >= 0.0
            assert run["recall_gain_vs_single"] == (run["recall"] - runs[0]["recall"])
        strict_gain = strict_gain or runs[-1]["recall"] > runs[0]["recall"]
    assert strict_gain


def test_benchmark_single_start_recall_matches_wave3_masks() -> None:
    report = _small_report()
    vectors = dense_vectors(SMALL["size"], SMALL["dimension"], SMALL["seed"])
    all_ids = sorted(vectors)
    exact = DenseFlatIndex(vectors)
    hnsw = HNSWIndex(vectors, m=SMALL["m"])
    queries = _queries(vectors, count=SMALL["query_count"])
    data = report["multistart_recall"]
    for row in data["by_allowlist_size"]:
        size = row["allowlist_size"]
        numerator = 0
        denominator = 0
        for position, query in enumerate(queries):
            allowed = _sampled_allowlist(
                all_ids, seed=SMALL["seed"], allowlist_size=size, position=position
            )
            exact_ids = {
                hit.document_id
                for hit in exact.search(
                    query, limit=SMALL["k"], allowed_document_ids=allowed
                )
            }
            hit_ids = {
                hit.document_id
                for hit in hnsw.search(
                    query,
                    limit=SMALL["k"],
                    ef_search=max(SMALL["ef_search"], SMALL["k"]),
                    allowed_document_ids=allowed,
                    search_starts=1,
                )
            }
            numerator += len(exact_ids & hit_ids)
            denominator += len(exact_ids)
        single = row["runs"][0]
        assert single["recall_numerator"] == numerator
        assert single["recall_denominator"] == denominator


def test_benchmark_search_starts_are_sorted_and_deduplicated() -> None:
    report = _small_report(search_starts=(8, 1, 4, 4))
    assert report["configuration"]["search_starts"] == [1, 4, 8]
    assert report["multistart_recall"]["search_starts"] == [1, 4, 8]


def test_run_benchmark_is_deterministic_when_timing_is_stripped() -> None:
    assert _strip_timing(_small_report()) == _strip_timing(_small_report())


def test_run_benchmark_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="at least two"):
        run_benchmark(size=1, search_starts=(1,))
    for bad in (0, -1, True, 1.5, None):
        with pytest.raises(ValueError, match="positive integers"):
            run_benchmark(size=16, search_starts=(bad,))
    for bad in (-1, 2.5, True):
        with pytest.raises(ValueError, match="non-negative integer"):
            run_benchmark(size=16, search_starts=(1,), exact_filter_threshold=bad)


def test_cli_writes_json_output(tmp_path) -> None:
    target = tmp_path / "nested" / "multistart.json"
    exit_code = main(
        [
            "--size",
            "120",
            "--dimension",
            "12",
            "--queries",
            "8",
            "--k",
            "8",
            "--seed",
            str(DEFAULT_SEED),
            "--m",
            "6",
            "--ef-search",
            "12",
            "--allowlist-sizes",
            "60",
            "120",
            "--search-starts",
            "1",
            "4",
            "--output",
            str(target),
        ]
    )
    assert exit_code == 0
    payload = json.loads(target.read_text())
    assert payload["configuration"]["size"] == 120
    assert payload["configuration"]["allowlist_sizes"] == [60, 120]
    assert payload["configuration"]["search_starts"] == [1, 4]
    data = payload["multistart_recall"]
    assert data["totals"]["unauthorized_hits"] == 0
    assert len(data["by_allowlist_size"]) == 2
    assert [run["search_starts"] for run in data["by_allowlist_size"][0]["runs"]] == [
        1,
        4,
    ]
