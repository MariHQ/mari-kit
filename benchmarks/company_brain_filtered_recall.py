#!/usr/bin/env python3
"""Deterministic exact-fallback recall experiments for filtered HNSW search.

``HNSWIndex`` supports an opt-in ``exact_filter_threshold``: when an
authorization allowlist is supplied and the effective allowed set is small,
search delegates to the exact ``DenseFlatIndex`` over just those authorized
vectors.  This runner answers the evidence question with the same deterministic
corpus and the same deterministic query/allowlist masks used by the wave-2
runner (``benchmarks/company_brain_recall.py``):

* What is the actual filtered recall of approximate HNSW search for each
  allowlist size?
* What does the exact fallback recover, and what does it cost in wall time?
* Are any unauthorized vectors ever scored or returned?

Timing is reported for the approximate search and the exact fallback search
separately, with the exact ground-truth recomputation timed independently so
the two sweeps stay comparable.
"""

from __future__ import annotations

import argparse
import json
import random
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from benchmarks.company_brain_recall import (
    DEFAULT_ALLOWLIST_SIZES,
    DEFAULT_DIMENSION,
    DEFAULT_EF_SEARCH,
    DEFAULT_K,
    DEFAULT_M,
    DEFAULT_QUERIES,
    DEFAULT_SEED,
    DEFAULT_SIZE,
    _query_vectors,
    dense_vectors,
)
from mari_kit.retrieval import DenseFlatIndex, HNSWIndex

DEFAULT_EXACT_FILTER_THRESHOLD = 8


def _sampled_allowlist(
    all_ids: Sequence[str], *, seed: int, allowlist_size: int, position: int
) -> set[str]:
    """Reproduce the wave-2 deterministic allowlist mask for one query."""

    return set(
        random.Random(f"{seed}:{allowlist_size}:{position}").sample(
            list(all_ids), allowlist_size
        )
    )


def _evaluate(
    exact: DenseFlatIndex,
    approximate: HNSWIndex,
    queries: Sequence[Sequence[float]],
    *,
    allowlist_size: int,
    all_ids: Sequence[str],
    k: int,
    ef_search: int,
    seed: int,
    exact_filter_threshold: int,
) -> dict[str, Any]:
    """Measure actual recall and search time for one allowlist size."""

    numerator = 0
    denominator = 0
    unauthorized = 0
    search_seconds = 0.0
    ground_truth_seconds = 0.0
    for position, query in enumerate(queries):
        allowed = _sampled_allowlist(
            all_ids, seed=seed, allowlist_size=allowlist_size, position=position
        )
        start = time.perf_counter()
        hits = approximate.search(
            query,
            limit=k,
            ef_search=max(ef_search, k),
            allowed_document_ids=allowed,
            exact_filter_threshold=exact_filter_threshold,
        )
        search_seconds += time.perf_counter() - start
        hit_ids = {hit.document_id for hit in hits}
        start = time.perf_counter()
        exact_ids = {
            hit.document_id
            for hit in exact.search(query, limit=k, allowed_document_ids=allowed)
        }
        ground_truth_seconds += time.perf_counter() - start
        numerator += len(exact_ids & hit_ids)
        denominator += len(exact_ids)
        unauthorized += len(hit_ids - allowed)
    return {
        "allowlist_size": allowlist_size,
        "queries": len(queries),
        "exact_filter_threshold": exact_filter_threshold,
        "fallback_engaged": (
            exact_filter_threshold > 0 and allowlist_size <= exact_filter_threshold
        ),
        "recall_numerator": numerator,
        "recall_denominator": denominator,
        "recall": (numerator / denominator) if denominator else None,
        "missed_relevant_hits": denominator - numerator,
        "unauthorized_hits": unauthorized,
        "timing_seconds": {
            "search": search_seconds,
            "ground_truth": ground_truth_seconds,
        },
    }


def _delta(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return left - right


def _ratio(left: float, right: float) -> float | None:
    return (left / right) if right else None


def _totals(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    numerator = sum(int(row["recall_numerator"]) for row in rows)
    denominator = sum(int(row["recall_denominator"]) for row in rows)
    return {
        "recall_numerator": numerator,
        "recall_denominator": denominator,
        "recall": (numerator / denominator) if denominator else None,
        "unauthorized_hits": sum(int(row["unauthorized_hits"]) for row in rows),
        "search_seconds": sum(float(row["timing_seconds"]["search"]) for row in rows),
        "ground_truth_seconds": sum(
            float(row["timing_seconds"]["ground_truth"]) for row in rows
        ),
    }


def filtered_fallback_recall(
    vectors: Mapping[str, Sequence[float]],
    *,
    seed: int,
    query_count: int,
    k: int,
    allowlist_sizes: Sequence[int],
    m: int,
    ef_search: int,
    exact_filter_threshold: int,
    metric: str = "cosine",
) -> dict[str, Any]:
    """Compare approximate HNSW against the exact fallback on identical masks."""

    dimension = len(next(iter(vectors.values())))
    all_ids = sorted(vectors)
    bounded_sizes = sorted(
        {max(1, min(size, len(all_ids))) for size in allowlist_sizes}
    )
    exact = DenseFlatIndex(vectors, metric=metric)
    build_start = time.perf_counter()
    approximate = HNSWIndex(vectors, m=m, metric=metric)
    build_seconds = time.perf_counter() - build_start
    queries = _query_vectors(vectors, count=query_count, dimension=dimension, seed=seed)
    approximate_rows = [
        _evaluate(
            exact,
            approximate,
            queries,
            allowlist_size=size,
            all_ids=all_ids,
            k=k,
            ef_search=ef_search,
            seed=seed,
            exact_filter_threshold=0,
        )
        for size in bounded_sizes
    ]
    fallback_rows = [
        _evaluate(
            exact,
            approximate,
            queries,
            allowlist_size=size,
            all_ids=all_ids,
            k=k,
            ef_search=ef_search,
            seed=seed,
            exact_filter_threshold=exact_filter_threshold,
        )
        for size in bounded_sizes
    ]
    by_allowlist_size = [
        {
            "allowlist_size": size,
            "fallback_engaged": bool(fallback["fallback_engaged"]),
            "approximate": approximate,
            "fallback": fallback,
            "recall_gain": _delta(fallback["recall"], approximate["recall"]),
            "timing_ratio": _ratio(
                float(fallback["timing_seconds"]["search"]),
                float(approximate["timing_seconds"]["search"]),
            ),
        }
        for size, approximate, fallback in zip(
            bounded_sizes, approximate_rows, fallback_rows, strict=True
        )
    ]
    approximate_totals = _totals(approximate_rows)
    fallback_totals = _totals(fallback_rows)
    return {
        "corpus_size": len(all_ids),
        "dimension": dimension,
        "metric": metric,
        "m": m,
        "k": k,
        "ef_search": max(ef_search, k),
        "exact_filter_threshold": exact_filter_threshold,
        "queries": query_count,
        "by_allowlist_size": by_allowlist_size,
        "totals": {
            "approximate": approximate_totals,
            "fallback": fallback_totals,
            "recall_gain": _delta(
                fallback_totals["recall"], approximate_totals["recall"]
            ),
            "unauthorized_hits": int(approximate_totals["unauthorized_hits"])
            + int(fallback_totals["unauthorized_hits"]),
        },
        "timing_seconds": {
            "hnsw_build": build_seconds,
            "approximate_sweep": approximate_totals["search_seconds"],
            "fallback_sweep": fallback_totals["search_seconds"],
            "ground_truth_sweeps": (
                float(approximate_totals["ground_truth_seconds"])
                + float(fallback_totals["ground_truth_seconds"])
            ),
        },
    }


def run_benchmark(
    *,
    size: int,
    dimension: int,
    query_count: int,
    k: int,
    seed: int,
    m: int,
    ef_search: int,
    allowlist_sizes: Sequence[int],
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
            "allowlist_sizes": sorted(
                {max(1, min(value, size)) for value in allowlist_sizes}
            ),
        },
        "filtered_fallback_recall": filtered_fallback_recall(
            vectors,
            seed=seed,
            query_count=query_count,
            k=k,
            allowlist_sizes=allowlist_sizes,
            m=m,
            ef_search=ef_search,
            exact_filter_threshold=exact_filter_threshold,
            metric=metric,
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", type=int, default=DEFAULT_SIZE)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--dimension", type=int, default=DEFAULT_DIMENSION)
    parser.add_argument("--queries", type=int, default=DEFAULT_QUERIES)
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
