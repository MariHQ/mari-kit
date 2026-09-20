#!/usr/bin/env python3
"""Deterministic multi-start recall experiments for filtered HNSW search.

``HNSWIndex.search`` gained an opt-in ``search_starts`` keyword: independent
bounded graph traversals are launched from deterministically chosen authorized
start nodes, and their scored candidates are merged before ranking.  This
runner answers the evidence question with the same deterministic corpus, the
same deterministic query vectors, and the same allowlist masks used by the
wave-3 filtered-recall runner (``benchmarks/company_brain_filtered_recall.py``
over ``benchmarks/company_brain_recall.py``):

* How much filtered recall does each ``search_starts`` value recover on the
  larger allowlists (200 and the full 1,000) relative to ``DenseFlatIndex``
  ground truth?
* What is the wall-time cost of the additional starts?
* Are any unauthorized vectors ever scored or returned?

The exact fallback stays disabled (``exact_filter_threshold=0``) so the measured
effect is multi-start graph search alone.  Ground truth is recomputed once per
allowlist size and reused across starts, and search time is accumulated with
``perf_counter`` around the index calls only.
"""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from benchmarks.company_brain_filtered_recall import _sampled_allowlist
from benchmarks.company_brain_recall import (
    DEFAULT_DIMENSION,
    DEFAULT_EF_SEARCH,
    DEFAULT_K,
    DEFAULT_M,
    DEFAULT_SEED,
    _query_vectors,
    dense_vectors,
)
from mari_kit.retrieval import DenseFlatIndex, HNSWIndex

WAVE3_SIZE = 1000
WAVE3_QUERIES = 20
DEFAULT_SIZE = WAVE3_SIZE
DEFAULT_QUERIES = WAVE3_QUERIES
DEFAULT_ALLOWLIST_SIZES = (200, 1000)
DEFAULT_SEARCH_STARTS = (1, 4, 8)
DEFAULT_EXACT_FILTER_THRESHOLD = 0


def _bounded_starts(search_starts: Sequence[int]) -> list[int]:
    for value in search_starts:
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError("search_starts must be positive integers")
    return sorted({value for value in search_starts})


def _bounded_sizes(allowlist_sizes: Sequence[int], corpus_size: int) -> list[int]:
    return sorted({max(1, min(int(value), corpus_size)) for value in allowlist_sizes})


def _evaluate(
    approximate: HNSWIndex,
    prepared: Sequence[tuple[Sequence[float], set[str], set[str]]],
    *,
    k: int,
    ef_search: int,
    search_starts: int,
    exact_filter_threshold: int,
) -> dict[str, Any]:
    """Measure recall and search latency for one start count.

    ``prepared`` holds the query, its allowlist mask, and the exact flat top-k
    IDs (ground truth) so the exact sweep is not re-timed per start count.
    """

    numerator = 0
    denominator = 0
    unauthorized = 0
    search_seconds = 0.0
    for query, allowed, exact_ids in prepared:
        start = time.perf_counter()
        hits = approximate.search(
            query,
            limit=k,
            ef_search=max(ef_search, k),
            allowed_document_ids=allowed,
            exact_filter_threshold=exact_filter_threshold,
            search_starts=search_starts,
        )
        search_seconds += time.perf_counter() - start
        hit_ids = {hit.document_id for hit in hits}
        numerator += len(exact_ids & hit_ids)
        denominator += len(exact_ids)
        unauthorized += len(hit_ids - allowed)
    return {
        "search_starts": search_starts,
        "queries": len(prepared),
        "recall_numerator": numerator,
        "recall_denominator": denominator,
        "recall": (numerator / denominator) if denominator else None,
        "missed_relevant_hits": denominator - numerator,
        "unauthorized_hits": unauthorized,
        "timing_seconds": {
            "search": search_seconds,
            "per_query": (search_seconds / len(prepared)) if prepared else None,
            "per_query_ms": (
                (1000.0 * search_seconds / len(prepared)) if prepared else None
            ),
        },
    }


def _delta(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return left - right


def _ratio(left: float | None, right: float | None) -> float | None:
    if left is None or right in (None, 0):
        return None
    return left / right


def multistart_recall(
    vectors: Mapping[str, Sequence[float]],
    *,
    seed: int,
    query_count: int,
    k: int,
    allowlist_sizes: Sequence[int],
    m: int,
    ef_search: int,
    search_starts: Sequence[int],
    exact_filter_threshold: int,
    metric: str = "cosine",
) -> dict[str, Any]:
    """Compare exact filtered top-k against multi-start HNSW per allowlist."""

    dimension = len(next(iter(vectors.values())))
    all_ids = sorted(vectors)
    bounded_sizes = _bounded_sizes(allowlist_sizes, len(all_ids))
    starts = _bounded_starts(search_starts)
    exact = DenseFlatIndex(vectors, metric=metric)
    build_start = time.perf_counter()
    approximate = HNSWIndex(vectors, m=m, metric=metric)
    build_seconds = time.perf_counter() - build_start
    queries = _query_vectors(vectors, count=query_count, dimension=dimension, seed=seed)

    by_allowlist_size: list[dict[str, Any]] = []
    ground_truth_seconds = 0.0
    total_unauthorized = 0
    total_search_seconds = 0.0
    for size in bounded_sizes:
        prepared: list[tuple[Sequence[float], set[str], set[str]]] = []
        for position, query in enumerate(queries):
            allowed = _sampled_allowlist(
                all_ids, seed=seed, allowlist_size=size, position=position
            )
            start = time.perf_counter()
            exact_ids = {
                hit.document_id
                for hit in exact.search(query, limit=k, allowed_document_ids=allowed)
            }
            ground_truth_seconds += time.perf_counter() - start
            prepared.append((query, allowed, exact_ids))
        runs = [
            _evaluate(
                approximate,
                prepared,
                k=k,
                ef_search=ef_search,
                search_starts=count,
                exact_filter_threshold=exact_filter_threshold,
            )
            for count in starts
        ]
        single = runs[0]
        recall_values = [float(run["recall"]) for run in runs]
        monotonic = all(
            right >= left
            for left, right in zip(recall_values, recall_values[1:], strict=False)
        )
        for run in runs:
            run["recall_gain_vs_single"] = _delta(run["recall"], single["recall"])
            run["latency_ratio_vs_single"] = _ratio(
                run["timing_seconds"]["search"], single["timing_seconds"]["search"]
            )
        total_unauthorized += sum(int(run["unauthorized_hits"]) for run in runs)
        total_search_seconds += sum(
            float(run["timing_seconds"]["search"]) for run in runs
        )
        by_allowlist_size.append(
            {
                "allowlist_size": size,
                "single_start": single["search_starts"],
                "recall_monotonic_in_starts": monotonic,
                "runs": runs,
            }
        )
    return {
        "corpus_size": len(all_ids),
        "dimension": dimension,
        "metric": metric,
        "m": m,
        "k": k,
        "ef_search": max(ef_search, k),
        "queries": query_count,
        "exact_filter_threshold": exact_filter_threshold,
        "search_starts": starts,
        "by_allowlist_size": by_allowlist_size,
        "totals": {
            "unauthorized_hits": total_unauthorized,
            "runs": len(bounded_sizes) * len(starts),
            "recall_monotonic_in_starts": all(
                row["recall_monotonic_in_starts"] for row in by_allowlist_size
            ),
        },
        "timing_seconds": {
            "hnsw_build": build_seconds,
            "multistart_sweeps": total_search_seconds,
            "ground_truth": ground_truth_seconds,
        },
    }


def run_benchmark(
    *,
    size: int = WAVE3_SIZE,
    dimension: int = DEFAULT_DIMENSION,
    query_count: int = WAVE3_QUERIES,
    k: int = DEFAULT_K,
    seed: int = DEFAULT_SEED,
    m: int = DEFAULT_M,
    ef_search: int = DEFAULT_EF_SEARCH,
    allowlist_sizes: Sequence[int] = DEFAULT_ALLOWLIST_SIZES,
    search_starts: Sequence[int] = DEFAULT_SEARCH_STARTS,
    exact_filter_threshold: int = DEFAULT_EXACT_FILTER_THRESHOLD,
    metric: str = "cosine",
) -> dict[str, Any]:
    if size < 2:
        raise ValueError("size must be at least two")
    if (
        isinstance(exact_filter_threshold, bool)
        or not isinstance(exact_filter_threshold, int)
        or exact_filter_threshold < 0
    ):
        raise ValueError("exact_filter_threshold must be a non-negative integer")
    starts = _bounded_starts(search_starts)
    vectors = dense_vectors(size, dimension, seed)
    return {
        "configuration": {
            "size": size,
            "dimension": dimension,
            "queries": query_count,
            "k": k,
            "seed": seed,
            "hnsw_m": m,
            "ef_search": max(ef_search, k),
            "metric": metric,
            "exact_filter_threshold": exact_filter_threshold,
            "allowlist_sizes": _bounded_sizes(allowlist_sizes, size),
            "search_starts": starts,
        },
        "multistart_recall": multistart_recall(
            vectors,
            seed=seed,
            query_count=query_count,
            k=k,
            allowlist_sizes=allowlist_sizes,
            m=m,
            ef_search=ef_search,
            search_starts=starts,
            exact_filter_threshold=exact_filter_threshold,
            metric=metric,
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", type=int, default=WAVE3_SIZE)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--dimension", type=int, default=DEFAULT_DIMENSION)
    parser.add_argument("--queries", type=int, default=WAVE3_QUERIES)
    parser.add_argument("--k", type=int, default=DEFAULT_K)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--m", type=int, default=DEFAULT_M)
    parser.add_argument("--ef-search", type=int, default=DEFAULT_EF_SEARCH)
    parser.add_argument(
        "--allowlist-sizes",
        type=int,
        nargs="+",
        default=list(DEFAULT_ALLOWLIST_SIZES),
    )
    parser.add_argument(
        "--search-starts",
        type=int,
        nargs="+",
        default=list(DEFAULT_SEARCH_STARTS),
    )
    parser.add_argument(
        "--exact-filter-threshold",
        type=int,
        default=DEFAULT_EXACT_FILTER_THRESHOLD,
    )
    parser.add_argument(
        "--metric",
        choices=("cosine", "dot", "l2"),
        default="cosine",
    )
    args = parser.parse_args(argv)
    report = run_benchmark(
        size=args.size,
        dimension=args.dimension,
        query_count=args.queries,
        k=args.k,
        seed=args.seed,
        m=args.m,
        ef_search=args.ef_search,
        allowlist_sizes=args.allowlist_sizes,
        search_starts=args.search_starts,
        exact_filter_threshold=args.exact_filter_threshold,
        metric=args.metric,
    )
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(text, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
        print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
