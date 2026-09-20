#!/usr/bin/env python3
"""Deterministic filtered-retrieval recall experiments for company brains.

The runner answers two evidence questions with recorded denominators rather
than anecdote:

* Exact ``DenseFlatIndex`` ground truth is compared against ``HNSWIndex``
  under sparse authorization allowlists.  We report recall numerator and
  denominator (``min(limit, allowlist_size)``) plus the number of hits that
  escaped the allowlist.
* ``BM25Index`` is exercised over a corpus with unique marker terms so the
  relevant document of every query is known before construction.  The same
  queries are evaluated before and after edits/deletions, and the
  incremental ``with_deltas`` snapshot is proven rebuild-equivalent to a
  fresh index over the final documents.

The runner only depends on public Mari retrieval APIs and is safe to invoke
at ``--size 1000`` (or larger) without any external service.
"""

from __future__ import annotations

import argparse
import json
import random
import time
from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy as np

from mari_kit.retrieval import (
    BM25Index,
    DenseFlatIndex,
    HNSWIndex,
    IndexDelta,
    IndexOperation,
)

DEFAULT_SEED = 20240919
DEFAULT_SIZE = 240
DEFAULT_DIMENSION = 24
DEFAULT_QUERIES = 32
DEFAULT_K = 10
DEFAULT_M = 8
DEFAULT_EF_SEARCH = 64
DEFAULT_ALLOWLIST_SIZES = (1, 2, 4, 8, 16, 32, 64)
FILLER_TERMS = (
    "alpha",
    "beta",
    "gamma",
    "delta",
    "epsilon",
    "zeta",
    "eta",
    "theta",
    "iota",
    "kappa",
)


def _document_ids(size: int, prefix: str) -> list[str]:
    width = max(4, len(str(max(size - 1, 0))))
    return [f"{prefix}-{index:0{width}d}" for index in range(size)]


def dense_vectors(size: int, dimension: int, seed: int) -> dict[str, list[float]]:
    """Return ``size`` deterministic Gaussian vectors keyed by stable ID."""

    rng = np.random.default_rng(seed)
    matrix = rng.standard_normal((size, dimension))
    return {
        identifier: row.tolist()
        for identifier, row in zip(_document_ids(size, "doc"), matrix, strict=True)
    }


def _query_vectors(
    vectors: Mapping[str, Sequence[float]],
    *,
    count: int,
    dimension: int,
    seed: int,
) -> list[list[float]]:
    """Half the queries perturb a corpus vector, half are fresh."""

    rng = np.random.default_rng([seed, 7])
    identifiers = sorted(vectors)
    queries: list[list[float]] = []
    for index in range(count):
        if index % 2 == 0 and identifiers:
            base = np.asarray(
                vectors[identifiers[(index * 13) % len(identifiers)]], dtype=np.float64
            )
            queries.append((base + 0.05 * rng.standard_normal(dimension)).tolist())
        else:
            queries.append(rng.standard_normal(dimension).tolist())
    return queries


def _recall_row(
    exact: DenseFlatIndex,
    approximate: HNSWIndex,
    queries: Sequence[Sequence[float]],
    *,
    allowlist_size: int,
    all_ids: Sequence[str],
    k: int,
    ef_search: int,
    seed: int,
) -> dict[str, object]:
    numerator = 0
    denominator = 0
    unauthorized = 0
    for position, query in enumerate(queries):
        allowed = set(
            random.Random(f"{seed}:{allowlist_size}:{position}").sample(
                list(all_ids), allowlist_size
            )
        )
        exact_hits = exact.search(query, limit=k, allowed_document_ids=allowed)
        approximate_hits = approximate.search(
            query, limit=k, ef_search=max(ef_search, k), allowed_document_ids=allowed
        )
        exact_ids = {hit.document_id for hit in exact_hits}
        approximate_ids = {hit.document_id for hit in approximate_hits}
        numerator += len(exact_ids & approximate_ids)
        denominator += len(exact_ids)
        unauthorized += len(approximate_ids - allowed)
    return {
        "allowlist_size": allowlist_size,
        "ef_search": max(ef_search, k),
        "queries": len(queries),
        "recall_numerator": numerator,
        "recall_denominator": denominator,
        "recall": (numerator / denominator) if denominator else None,
        "missed_relevant_hits": denominator - numerator,
        "unauthorized_hits": unauthorized,
    }


def filtered_dense_recall(
    vectors: Mapping[str, Sequence[float]],
    *,
    seed: int,
    query_count: int,
    k: int,
    allowlist_sizes: Sequence[int],
    m: int,
    ef_search: int,
    metric: str = "cosine",
) -> dict[str, object]:
    """Compare exact filtered top-k against HNSW under sparse allowlists."""

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
    query_start = time.perf_counter()
    rows = [
        _recall_row(
            exact,
            approximate,
            queries,
            allowlist_size=size,
            all_ids=all_ids,
            k=k,
            ef_search=ef_search,
            seed=seed,
        )
        for size in bounded_sizes
    ]
    sparse_size = max(1, min(4, len(all_ids)))
    sweep_sizes = sorted({sparse_size, len(all_ids)})
    sweep_ef = sorted({k, max(64, k), max(256, k)})
    ef_search_sensitivity = [
        _recall_row(
            exact,
            approximate,
            queries,
            allowlist_size=size,
            all_ids=all_ids,
            k=k,
            ef_search=ef,
            seed=seed,
        )
        for size in sweep_sizes
        for ef in sweep_ef
    ]
    query_seconds = time.perf_counter() - query_start
    total_numerator = sum(int(row["recall_numerator"]) for row in rows)
    total_denominator = sum(int(row["recall_denominator"]) for row in rows)
    return {
        "corpus_size": len(all_ids),
        "dimension": dimension,
        "metric": metric,
        "m": m,
        "k": k,
        "by_allowlist_size": rows,
        "ef_search_sensitivity": ef_search_sensitivity,
        "totals": {
            "recall_numerator": total_numerator,
            "recall_denominator": total_denominator,
            "recall": (
                total_numerator / total_denominator if total_denominator else None
            ),
            "unauthorized_hits": sum(int(row["unauthorized_hits"]) for row in rows),
        },
        "timing_seconds": {
            "hnsw_build": build_seconds,
            "filtered_query": query_seconds,
        },
    }


def lexical_corpus(
    size: int, seed: int
) -> tuple[dict[str, str], dict[str, str], list[str]]:
    """Documents with one unique marker token each, so relevance is known."""

    rng = random.Random(seed)
    documents: dict[str, str] = {}
    revisions: dict[str, str] = {}
    markers: list[str] = []
    for identifier in _document_ids(size, "lex"):
        marker = f"marker{len(markers):04d}x"
        words = rng.sample(FILLER_TERMS, 3)
        documents[identifier] = " ".join((*words, marker, "policy", "handbook"))
        revisions[identifier] = "1"
        markers.append(marker)
    return documents, revisions, markers


def _positive_hits(
    index: BM25Index,
    query: str,
    *,
    limit: int,
    allowed: Sequence[str] | None = None,
) -> list[str]:
    hits = index.search(query, limit=limit, allowed_document_ids=allowed)
    return [hit.document_id for hit in hits if hit.score > 0]


def _ranking(index: BM25Index, query: str, *, limit: int) -> list[tuple[str, float]]:
    return [
        (hit.document_id, round(hit.score, 12))
        for hit in index.search(query, limit=limit)
    ]


def _known_relevant_recall(
    index: BM25Index,
    probes: Sequence[tuple[str, set[str]]],
    *,
    k: int,
) -> dict[str, object]:
    """Recall of known relevant sets with an explicit denominator.

    Queries whose relevant set is empty contribute only to the stale/local
    false-positive count; they never inflate the denominator.
    """

    numerator = 0
    denominator = 0
    unexpected = 0
    rows: list[dict[str, object]] = []
    for query, relevant in probes:
        positive = set(_positive_hits(index, query, limit=k))
        if relevant:
            numerator += len(positive & relevant)
            denominator += len(relevant)
        unexpected += len(positive - relevant)
        rows.append(
            {
                "query": query,
                "relevant": sorted(relevant),
                "positive_hits": sorted(positive),
                "recall_numerator": len(positive & relevant) if relevant else 0,
                "recall_denominator": len(relevant),
            }
        )
    return {
        "queries": len(probes),
        "recall_numerator": numerator,
        "recall_denominator": denominator,
        "recall": (numerator / denominator) if denominator else None,
        "unexpected_positive_hits": unexpected,
        "rows": rows,
    }


def _apply(documents: dict[str, str], revisions: dict[str, str], deltas) -> None:
    for delta in deltas:
        if delta.operation is IndexOperation.DELETE:
            documents.pop(delta.item_id, None)
            revisions.pop(delta.item_id, None)
        else:
            documents[delta.item_id] = delta.text
            revisions[delta.item_id] = delta.revision


def bm25_lifecycle(
    size: int, *, seed: int, k: int, probe_limit: int
) -> dict[str, object]:
    """Known-relevant BM25 recall before/after edits and deletions.

    Proves that ``with_deltas`` produces a snapshot rebuild-equivalent to a
    fresh index over the final documents.
    """

    documents, revisions, markers = lexical_corpus(size, seed)
    if size < 2:
        raise ValueError("bm25_lifecycle requires at least two documents")
    base = BM25Index(documents, revisions=revisions)
    edited_id = _document_ids(size, "lex")[0]
    deleted_id = _document_ids(size, "lex")[1]
    inserted_id = "lex-inserted"
    edited_old_marker = markers[0]
    deleted_old_marker = markers[1]
    edited_new_marker = "quokka9001x"
    inserted_marker = "narwhal9002x"

    before = {
        "edited_marker": _positive_hits(base, edited_old_marker, limit=k),
        "deleted_marker": _positive_hits(base, deleted_old_marker, limit=k),
        "edited_new_marker": _positive_hits(base, edited_new_marker, limit=k),
        "inserted_marker": _positive_hits(base, inserted_marker, limit=k),
    }

    first_batch = (
        IndexDelta(
            item_id=edited_id,
            operation=IndexOperation.UPSERT,
            revision="2",
            text=f"quokka {edited_new_marker} policy handbook update",
            expected_revision="1",
        ),
        IndexDelta(
            item_id=deleted_id,
            operation=IndexOperation.DELETE,
            expected_revision="1",
        ),
    )
    second_batch = (
        IndexDelta(
            item_id=inserted_id,
            operation=IndexOperation.UPSERT,
            revision="1",
            text=f"narwhal {inserted_marker} policy",
        ),
    )
    incremental = base.with_deltas(first_batch).with_deltas(second_batch)

    after = {
        "edited_old_marker": _positive_hits(incremental, edited_old_marker, limit=k),
        "deleted_old_marker": _positive_hits(incremental, deleted_old_marker, limit=k),
        "edited_new_marker": _positive_hits(incremental, edited_new_marker, limit=k),
        "inserted_marker": _positive_hits(incremental, inserted_marker, limit=k),
    }
    recall_before = _known_relevant_recall(
        base,
        (
            (edited_old_marker, {edited_id}),
            (deleted_old_marker, {deleted_id}),
            (edited_new_marker, set()),
            (inserted_marker, set()),
        ),
        k=k,
    )
    recall_after = _known_relevant_recall(
        incremental,
        (
            (edited_old_marker, set()),
            (deleted_old_marker, set()),
            (edited_new_marker, {edited_id}),
            (inserted_marker, {inserted_id}),
        ),
        k=k,
    )
    deleted_document_visible = any(
        hit.document_id == deleted_id
        for hit in incremental.search(deleted_old_marker, limit=probe_limit)
    )
    restricted_allowed = [
        identifier for identifier in documents if identifier != edited_id
    ]
    restricted_positive = _positive_hits(
        incremental,
        edited_new_marker,
        limit=k,
        allowed=restricted_allowed,
    )
    unauthorized = [
        hit.document_id
        for hit in incremental.search(
            edited_new_marker, limit=k, allowed_document_ids=restricted_allowed
        )
        if hit.document_id not in set(restricted_allowed)
    ]

    final_documents = dict(base.documents)
    final_revisions = dict(base.revisions)
    _apply(final_documents, final_revisions, (*first_batch, *second_batch))
    fresh = BM25Index(
        final_documents,
        revisions=final_revisions,
        k1=base.k1,
        b=base.b,
        analyzer=base.analyzer,
    )
    single = base.with_deltas((*first_batch, *second_batch))

    probe_queries = (
        edited_old_marker,
        deleted_old_marker,
        edited_new_marker,
        inserted_marker,
        "policy",
        "handbook",
        *FILLER_TERMS,
    )
    mismatches: list[dict[str, object]] = []
    for query in probe_queries:
        incremental_ranking = _ranking(incremental, query, limit=probe_limit)
        fresh_ranking = _ranking(fresh, query, limit=probe_limit)
        single_ranking = _ranking(single, query, limit=probe_limit)
        if incremental_ranking != fresh_ranking or single_ranking != fresh_ranking:
            mismatches.append(
                {
                    "query": query,
                    "incremental": incremental_ranking,
                    "fresh": fresh_ranking,
                    "single_batch": single_ranking,
                }
            )
    return {
        "corpus_size": size,
        "k": k,
        "before": before,
        "after": after,
        "recall_before": recall_before,
        "recall_after": recall_after,
        "deleted_document_visible": deleted_document_visible,
        "restricted_query": {
            "allowlist_size": len(restricted_allowed),
            "positive_hits": restricted_positive,
            "unauthorized_hits": len(unauthorized),
        },
        "rebuild_equivalence": {
            "queries_compared": len(probe_queries),
            "documents_equal": incremental.documents == fresh.documents,
            "revisions_equal": incremental.revisions == fresh.revisions,
            "rankings_equal": not mismatches,
            "mismatches": mismatches,
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
) -> dict[str, object]:
    if size < 2:
        raise ValueError("size must be at least two")
    vectors = dense_vectors(size, dimension, seed)
    return {
        "configuration": {
            "size": size,
            "dimension": dimension,
            "queries": query_count,
            "k": k,
            "seed": seed,
            "hnsw_m": m,
            "ef_search": ef_search,
            "allowlist_sizes": sorted(
                {max(1, min(value, size)) for value in allowlist_sizes}
            ),
        },
        "dense_filtered_recall": filtered_dense_recall(
            vectors,
            seed=seed,
            query_count=query_count,
            k=k,
            allowlist_sizes=allowlist_sizes,
            m=m,
            ef_search=ef_search,
        ),
        "lexical_lifecycle": bm25_lifecycle(
            size, seed=seed, k=k, probe_limit=max(k, 2)
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
