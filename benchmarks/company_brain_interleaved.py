#!/usr/bin/env python3
"""Deterministic interleaved multi-user workload benchmark for a company brain.

Service traffic rarely groups one user's questions together.  This benchmark
feeds the *same multiset* of ``(user, query)`` requests to a freshly seeded
:class:`CompanyBrain` over an :class:`SQLiteBrainStore` in three different
orders and measures what the bounded authorized-view cache does:

* ``consecutive`` -- each user's queries run back to back before the next user;
* ``round_robin`` -- one query per user, cycling by query index;
* ``hot_interleaved`` -- one hot user's queries are spread through the run and
  separated by even blocks of cold-user traffic; each block holds whole users,
  so the hot view is repeatedly pushed out by other users rather than by
  per-request churn.

All three orderings are permutations of the identical request multiset, so any
difference is attributable to interleaving alone.  The benchmark uses the
existing deterministic corpus helpers (``build_documents`` from
``benchmarks/company_brain_scale.py`` and ``build_users`` /
``build_user_queries`` from ``benchmarks/company_brain_cache_memory.py``), so a
fixed seed reproduces the corpus, the user/group assignments, the queries, and
the request orderings exactly.

For each ordering it records, from a counting store subclass and the engine
itself:

* the **actual** number of ``access_token_snapshot`` calls (a view-cache miss
  rebuilds exactly one authorized view, so misses are counted, never assumed);
* view-cache hits as ``requests - misses`` and the derived hit rate;
* ``CompanyBrain.cache_stats()`` (retained-view count and estimated bytes,
  evictions) and whether the configured count bound and retained-byte budget
  held;
* per-request wall samples with p50/p95 and the sample count.

Wall seconds are reported for context only; no machine-time threshold is ever
applied.  The durable engine and store are imported lazily and the CLI exits
with a clear message when the reference application is absent.

Run it with the repository virtual environment:

    .venv/bin/python -m benchmarks.company_brain_interleaved --output report.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from benchmarks.company_brain_cache_memory import build_user_queries, build_users
from benchmarks.company_brain_scale import build_documents, latency_summary
from mari_kit import PollPage, ScopeRef, SyncMode
from mari_kit.sync import plan_sync

BENCHMARK_SCHEMA = "mari-kit.company-brain-interleaved-workload/1"
DEFAULT_SEED = 20240919
DEFAULT_DOCUMENTS = 240
DEFAULT_USERS = 16
DEFAULT_QUERIES_PER_USER = 4
DEFAULT_LIMIT = 5
DEFAULT_VIEW_CACHE_SIZE = 8
DEFAULT_VIEW_CACHE_BYTES = 2 * 1024 * 1024
STRATEGIES = ("consecutive", "round_robin", "hot_interleaved")
SCOPE = ScopeRef(tenant="interleaved", space="workload")


def engine_available() -> bool:
    """Return ``True`` when the durable store/engine module is importable."""

    try:
        import examples.company_brains.durable.engine  # noqa: F401
        import examples.company_brains.durable.store  # noqa: F401
    except Exception:
        return False
    return True


def _positive(name: str, value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return int(value)


def _non_negative(
    name: str, value: int | None, *, allow_none: bool = False
) -> int | None:
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return int(value)


def _distribute(
    hot: Sequence[tuple[str, str]], cold: Sequence[tuple[str, str]]
) -> tuple[tuple[str, str], ...]:
    """Spread ``cold`` requests evenly between the ``hot`` requests.

    The hot and cold subsequences keep their relative order, so the result is a
    permutation of ``(*hot, *cold)`` however the two lengths divide.
    """

    hot_items = list(hot)
    cold_items = list(cold)
    if not hot_items:
        return tuple(cold_items)
    stride, extra = divmod(len(cold_items), len(hot_items))
    ordered: list[tuple[str, str]] = []
    index = 0
    for position, item in enumerate(hot_items):
        ordered.append(item)
        size = stride + (1 if position < extra else 0)
        ordered.extend(cold_items[index : index + size])
        index += size
    ordered.extend(cold_items[index:])
    return tuple(ordered)


def request_orderings(
    user_specs: Sequence[tuple[str, tuple[str, ...]]],
    *,
    queries_per_user: int,
    seed: int,
    hot_user: str | None = None,
) -> dict[str, tuple[tuple[str, str], ...]]:
    """Build the three request orderings over one identical request multiset.

    ``user_specs`` is the ``(user_id, groups)`` sequence returned by
    ``build_users``; only the user ids are used here.
    """

    if not user_specs:
        raise ValueError("user_specs must not be empty")
    queries_per_user = _positive("queries_per_user", queries_per_user)
    user_ids = tuple(user_id for user_id, _groups in user_specs)
    if len(set(user_ids)) != len(user_ids):
        raise ValueError("user ids must be unique")
    if hot_user is None:
        hot_user = user_ids[0]
    if hot_user not in user_ids:
        raise ValueError("hot_user must be one of the supplied user ids")

    per_user = tuple(
        (
            user_id,
            build_user_queries(user_id, queries_per_user, seed=seed),
        )
        for user_id in user_ids
    )
    if any(len(queries) != queries_per_user for _user, queries in per_user):
        raise ValueError("every user must receive exactly queries_per_user queries")

    consecutive = tuple(
        (user_id, query) for user_id, queries in per_user for query in queries
    )
    round_robin = tuple(
        (user_id, queries[index])
        for index in range(queries_per_user)
        for user_id, queries in per_user
    )
    hot_requests = tuple(
        (user_id, query)
        for user_id, queries in per_user
        if user_id == hot_user
        for query in queries
    )
    cold_requests = tuple(
        (user_id, query)
        for user_id, queries in per_user
        if user_id != hot_user
        for query in queries
    )
    return {
        "consecutive": consecutive,
        "round_robin": round_robin,
        "hot_interleaved": _distribute(hot_requests, cold_requests),
    }


def _fingerprint(requests: Sequence[tuple[str, str]]) -> str:
    payload = json.dumps(
        sorted(requests), ensure_ascii=False, separators=(",", ":")
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _user_switches(requests: Sequence[tuple[str, str]]) -> int:
    return sum(
        1
        for previous, current in zip(requests, requests[1:], strict=False)
        if previous[0] != current[0]
    )


def _sync(store: Any, scope: ScopeRef, documents: Sequence[Any]) -> None:
    grouped: dict[str, list[Any]] = {}
    for document in documents:
        grouped.setdefault(document.source_id, []).append(document)
    for source, source_documents in grouped.items():
        plan = plan_sync(
            store.state(scope, source),
            PollPage(upserts=tuple(source_documents), snapshot_complete=True),
            source_id=source,
            mode=SyncMode.FULL,
        )
        store.apply_plan(scope, plan)


def _execute_strategy(
    directory: Path,
    name: str,
    requests: Sequence[tuple[str, str]],
    corpus: Sequence[Any],
    user_specs: Sequence[tuple[str, tuple[str, ...]]],
    *,
    limit: int,
    view_cache_size: int,
    view_cache_bytes: int | None,
) -> dict[str, Any]:
    from examples.company_brains.durable.engine import CompanyBrain
    from examples.company_brains.durable.store import SQLiteBrainStore

    class _CountingStore(SQLiteBrainStore):
        """Counts cheap token reads and authorized-view rebuilds exactly."""

        def __init__(self, path: object) -> None:
            super().__init__(path)  # type: ignore[arg-type]
            self.access_token_reads = 0
            self.snapshot_reads = 0

        def access_token(self, scope: ScopeRef, user_id: str):  # type: ignore[no-untyped-def]
            self.access_token_reads += 1
            return super().access_token(scope, user_id)

        def access_token_snapshot(self, scope: ScopeRef, user_id: str):  # type: ignore[no-untyped-def]
            self.snapshot_reads += 1
            return super().access_token_snapshot(scope, user_id)

    store = _CountingStore(directory)
    try:
        _sync(store, SCOPE, corpus)
        for user_id, groups in user_specs:
            store.set_groups(SCOPE, user_id, groups)
        brain = CompanyBrain(
            store,
            SCOPE,
            view_cache_size=view_cache_size,
            view_cache_bytes=view_cache_bytes,
        )
        samples: list[float] = []
        for user_id, query in requests:
            started = time.perf_counter()
            brain.search(query, user_id=user_id, limit=limit)
            samples.append(time.perf_counter() - started)
        stats = brain.cache_stats()
        misses = store.snapshot_reads
        token_reads = store.access_token_reads
    finally:
        store.close()

    total = len(requests)
    hits = total - misses
    within_count_bound = stats.views <= view_cache_size
    within_byte_budget = (
        view_cache_bytes is None or stats.retained_estimated_bytes <= view_cache_bytes
    )
    return {
        "name": name,
        "requests": total,
        "view_misses": misses,
        "view_hits": hits,
        "hit_rate": round(hits / total, 6) if total else None,
        "access_token_reads": token_reads,
        "cache_stats": {
            "views": stats.views,
            "retained_estimated_bytes": stats.retained_estimated_bytes,
            "evictions": stats.evictions,
            "evicted_estimated_bytes": stats.evicted_estimated_bytes,
            "max_views": stats.max_views,
            "max_bytes": stats.max_bytes,
        },
        "within_count_bound": within_count_bound,
        "within_byte_budget": within_byte_budget,
        "within_bounds": within_count_bound and within_byte_budget,
        "latency": latency_summary(samples),
        "latency_samples_seconds": [round(sample, 6) for sample in samples],
        "miss_note": (
            "view_misses is the counted number of access_token_snapshot calls: "
            "a view-cache miss rebuilds exactly one authorized view. view_hits "
            "is requests - view_misses (no synthetic counts)."
        ),
    }


def _execute_all(
    base: Path,
    orderings: dict[str, tuple[tuple[str, str], ...]],
    corpus: Sequence[Any],
    user_specs: Sequence[tuple[str, tuple[str, ...]]],
    *,
    limit: int,
    view_cache_size: int,
    view_cache_bytes: int | None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for name in STRATEGIES:
        directory = base / name
        directory.mkdir(parents=True, exist_ok=True)
        results.append(
            _execute_strategy(
                directory,
                name,
                orderings[name],
                corpus,
                user_specs,
                limit=limit,
                view_cache_size=view_cache_size,
                view_cache_bytes=view_cache_bytes,
            )
        )
    return results


def run(
    *,
    documents: int = DEFAULT_DOCUMENTS,
    users: int = DEFAULT_USERS,
    queries_per_user: int = DEFAULT_QUERIES_PER_USER,
    limit: int = DEFAULT_LIMIT,
    view_cache_size: int = DEFAULT_VIEW_CACHE_SIZE,
    view_cache_bytes: int | None = DEFAULT_VIEW_CACHE_BYTES,
    seed: int = DEFAULT_SEED,
    hot_user: str | None = None,
    workdir: str | Path | None = None,
) -> dict[str, Any]:
    """Run the interleaved workload and return a JSON-serializable report."""

    from examples.company_brains.durable.engine import authorized_documents

    documents = _positive("documents", documents)
    users = _positive("users", users)
    queries_per_user = _positive("queries_per_user", queries_per_user)
    limit = _positive("limit", limit)
    view_cache_size = _non_negative("view_cache_size", view_cache_size)
    view_cache_bytes = _non_negative(
        "view_cache_bytes", view_cache_bytes, allow_none=True
    )

    corpus = build_documents(documents, seed=seed)
    user_specs = build_users(users, seed=seed)
    orderings = request_orderings(
        user_specs,
        queries_per_user=queries_per_user,
        seed=seed,
        hot_user=hot_user,
    )
    resolved_hot_user = hot_user if hot_user is not None else user_specs[0][0]

    authorized_counts = [
        len(authorized_documents(corpus, user_id=user_id, groups=set(groups)))
        for user_id, groups in user_specs
    ]
    fingerprints = {name: _fingerprint(reqs) for name, reqs in orderings.items()}
    workloads = {
        name: {
            "requests": len(requests),
            "fingerprint": fingerprints[name],
            "user_switches": _user_switches(requests),
            "sequence": [[user_id, query] for user_id, query in requests],
        }
        for name, requests in orderings.items()
    }
    multiset_equal = len(set(fingerprints.values())) == 1

    if workdir is not None:
        base = Path(tempfile.mkdtemp(prefix="interleaved-", dir=str(workdir)))
        strategies = _execute_all(
            base,
            orderings,
            corpus,
            user_specs,
            limit=limit,
            view_cache_size=view_cache_size,
            view_cache_bytes=view_cache_bytes,
        )
    else:
        with tempfile.TemporaryDirectory(
            prefix="company-brain-interleaved-"
        ) as temporary:
            strategies = _execute_all(
                Path(temporary),
                orderings,
                corpus,
                user_specs,
                limit=limit,
                view_cache_size=view_cache_size,
                view_cache_bytes=view_cache_bytes,
            )

    return {
        "schema": BENCHMARK_SCHEMA,
        "seed": seed,
        "configuration": {
            "documents": documents,
            "sources": len({document.source_id for document in corpus}),
            "users": users,
            "queries_per_user": queries_per_user,
            "limit": limit,
            "view_cache_size": view_cache_size,
            "view_cache_bytes": view_cache_bytes,
            "requests_per_strategy": len(orderings["consecutive"]),
            "hot_user": resolved_hot_user,
            "strategies": list(STRATEGIES),
            "operation": "CompanyBrain.search(query, user_id=..., limit=...)",
        },
        "workload": {
            "request_multiset_size": len(orderings["consecutive"]),
            "request_multiset_fingerprint": fingerprints["consecutive"],
            "request_multiset_equal": multiset_equal,
            "orderings": workloads,
            "note": (
                "All orderings are permutations of the same (user, query) "
                "multiset; equal fingerprints prove that."
            ),
        },
        "authorized_documents": {
            "min": min(authorized_counts),
            "max": max(authorized_counts),
            "mean": round(sum(authorized_counts) / len(authorized_counts), 3),
        },
        "strategies": strategies,
        "totals": {
            "requests": sum(row["requests"] for row in strategies),
            "view_misses": sum(row["view_misses"] for row in strategies),
            "view_hits": sum(row["view_hits"] for row in strategies),
        },
        "notes": {
            "miss_and_hit_note": (
                "view_misses counts real access_token_snapshot calls; view_hits "
                "is requests - misses. Nothing is synthesized."
            ),
            "latency_note": (
                "No machine-time threshold is applied. latency is informational; "
                "p95 is meaningful only when the reported count reaches the "
                "p95_valid threshold (>= 20 samples)."
            ),
            "memory_note": (
                "retained_estimated_bytes is the engine's explicit object-size "
                "estimate, not RSS; the byte budget uses the same estimate."
            ),
        },
    }


def deterministic_signature(report: dict[str, Any]) -> str:
    """Return a stable digest of everything except wall-clock measurements."""

    payload = json.loads(json.dumps(report, sort_keys=True))
    for strategy in payload.get("strategies", []):
        strategy.pop("latency", None)
        strategy.pop("latency_samples_seconds", None)
    payload.pop("elapsed_seconds", None)
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _positive_arg(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return number


def _non_negative_arg(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("value must not be negative")
    return number


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--documents", type=_positive_arg, default=DEFAULT_DOCUMENTS)
    parser.add_argument("--users", type=_positive_arg, default=DEFAULT_USERS)
    parser.add_argument(
        "--queries-per-user", type=_positive_arg, default=DEFAULT_QUERIES_PER_USER
    )
    parser.add_argument("--limit", type=_positive_arg, default=DEFAULT_LIMIT)
    parser.add_argument(
        "--count", type=_non_negative_arg, default=DEFAULT_VIEW_CACHE_SIZE
    )
    parser.add_argument(
        "--budget",
        type=_non_negative_arg,
        default=DEFAULT_VIEW_CACHE_BYTES,
        help="retained-byte budget for cached views",
    )
    parser.add_argument(
        "--no-byte-budget",
        dest="byte_budget",
        action="store_false",
        default=True,
        help="disable the retained-byte budget and exercise the count bound alone",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--hot-user", default=None)
    parser.add_argument("--workdir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    if not engine_available():
        raise SystemExit(
            "durable store/engine is not importable: "
            "examples.company_brains.durable.{store,engine}"
        )

    report = run(
        documents=args.documents,
        users=args.users,
        queries_per_user=args.queries_per_user,
        limit=args.limit,
        view_cache_size=args.count,
        view_cache_bytes=(args.budget if args.byte_budget else None),
        seed=args.seed,
        hot_user=args.hot_user,
        workdir=args.workdir,
    )
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
        print(f"wrote {args.output}")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
