"""Reproducible memory benchmark for the durable company-brain view cache.

The wave-3 cache bounded the number of authorized views a ``CompanyBrain``
retains.  For a service serving many users that count bound alone still lets the
process pin an unbounded amount of document text, because each view holds the
authorized documents, their fingerprints, a ``ref -> document`` map, and (after
first use) a BM25 index.  This benchmark exercises the wave-4 approximate
retained-byte budget alongside the count bound with a deterministic mixed-ACL
corpus and many users.

For one configuration it reports, separately:

* ``retained_estimated_bytes`` -- the engine's explicit retained-size estimate
  summed over the cached views (see ``ViewCacheStats``); it is *not* RSS.
* ``tracemalloc.retained_bytes`` / ``tracemalloc.peak_bytes`` -- tracemalloc's
  actual retained and peak traced allocations for the brain and its cache.
* hit behavior -- requests, misses (authorized-view rebuilds), hits, hit rate,
  and evictions.

Every input is deterministic for a fixed ``--seed``.  Wall seconds are reported
for context only and are never used as a pass/fail threshold.

The benchmark imports the durable store and engine lazily and exits with a clear
message when those sibling modules are absent.  Use ``--no-tracemalloc`` to skip
allocation tracing, or run the module directly:

    .venv/bin/python -m benchmarks.company_brain_cache_memory --output report.json
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import random
import tempfile
import time
import tracemalloc
from collections.abc import Sequence
from pathlib import Path

from benchmarks.company_brain_scale import TEAMS, VOCABULARY, build_documents
from mari_kit import PollPage, ScopeRef, SyncMode
from mari_kit.sync import plan_sync

BENCHMARK_SCHEMA = "mari-kit.company-brain-cache-memory/1"
DEFAULT_SEED = 20240919
DEFAULT_DOCUMENTS = 240
DEFAULT_USERS = 96
DEFAULT_QUERIES_PER_USER = 4
DEFAULT_LIMIT = 5
DEFAULT_VIEW_CACHE_SIZE = 12
DEFAULT_VIEW_CACHE_BYTES = 3 * 1024 * 1024


def _stable_random(*parts: object) -> random.Random:
    """Return a generator whose stream depends only on the supplied parts."""

    payload = ":".join(str(part) for part in parts).encode()
    digest = hashlib.sha256(payload).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def build_users(
    count: int, *, seed: int = DEFAULT_SEED
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Build ``count`` deterministic users with mixed group memberships."""

    if count < 1:
        raise ValueError("count must be positive")
    users: list[tuple[str, tuple[str, ...]]] = []
    for index in range(count):
        rng = _stable_random("user", seed, index)
        groups = tuple(sorted(rng.sample(TEAMS, rng.randint(0, len(TEAMS)))))
        users.append((f"user-{index:05d}", groups))
    return tuple(users)


def build_user_queries(
    user_id: str, count: int, *, seed: int = DEFAULT_SEED
) -> tuple[str, ...]:
    """Build deterministic one-to-three term lexical queries for one user."""

    if count < 1:
        raise ValueError("count must be positive")
    rng = _stable_random("queries", seed, user_id)
    return tuple(
        " ".join(rng.choice(VOCABULARY) for _ in range(rng.randint(1, 3)))
        for _ in range(count)
    )


def engine_available() -> bool:
    try:
        import examples.company_brains.durable.engine  # noqa: F401
        import examples.company_brains.durable.store  # noqa: F401
    except Exception:
        return False
    return True


def _sync(store, scope: ScopeRef, documents: Sequence) -> None:
    grouped: dict[str, list] = {}
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


def run(
    *,
    documents: int = DEFAULT_DOCUMENTS,
    users: int = DEFAULT_USERS,
    queries_per_user: int = DEFAULT_QUERIES_PER_USER,
    limit: int = DEFAULT_LIMIT,
    view_cache_size: int = DEFAULT_VIEW_CACHE_SIZE,
    view_cache_bytes: int | None = DEFAULT_VIEW_CACHE_BYTES,
    seed: int = DEFAULT_SEED,
    tracemalloc_enabled: bool = True,
    workdir: str | Path | None = None,
) -> dict:
    """Run one bounded-cache configuration and return a JSON-serializable report."""

    from examples.company_brains.durable.engine import (
        CompanyBrain,
        authorized_documents,
    )
    from examples.company_brains.durable.store import SQLiteBrainStore

    if documents < 1 or users < 1 or queries_per_user < 1:
        raise ValueError("documents, users, and queries_per_user must be positive")
    if view_cache_size < 0:
        raise ValueError("view_cache_size must not be negative")
    if view_cache_bytes is not None and view_cache_bytes < 0:
        raise ValueError("view_cache_bytes must not be negative")

    scope = ScopeRef(tenant="cache-memory", space="company")
    corpus = build_documents(documents, seed=seed)
    user_specs = build_users(users, seed=seed)
    requests = tuple(
        (user_id, query)
        for user_id, _groups in user_specs
        for query in build_user_queries(user_id, queries_per_user, seed=seed)
    )
    authorized_counts = [
        len(authorized_documents(corpus, user_id=user_id, groups=set(groups)))
        for user_id, groups in user_specs
    ]

    def _execute(directory: Path) -> dict:
        class _CountingStore(SQLiteBrainStore):
            """Counts authorized-view rebuilds via token snapshot reads."""

            def __init__(self, path: object) -> None:
                super().__init__(path)  # type: ignore[arg-type]
                self.snapshot_reads = 0

            def access_token_snapshot(self, scope: ScopeRef, user_id: str):  # type: ignore[no-untyped-def]
                self.snapshot_reads += 1
                return super().access_token_snapshot(scope, user_id)

        database = directory / "brain.sqlite"
        store = _CountingStore(database)
        try:
            _sync(store, scope, corpus)
            for user_id, groups in user_specs:
                store.set_groups(scope, user_id, groups)

            gc.collect()
            if tracemalloc_enabled:
                tracemalloc.start()
                tracemalloc.reset_peak()
            store.snapshot_reads = 0
            started = time.perf_counter()
            brain = CompanyBrain(
                store,
                scope,
                view_cache_size=view_cache_size,
                view_cache_bytes=view_cache_bytes,
            )
            for user_id, query in requests:
                brain.search(query, user_id=user_id, limit=limit)
            elapsed = time.perf_counter() - started
            stats = brain.cache_stats()
            if tracemalloc_enabled:
                retained, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
            else:
                retained = peak = None
            # Each cache miss rebuilds one authorized view and therefore
            # performs exactly one access-token snapshot read; hits perform none.
            misses = store.snapshot_reads
        finally:
            store.close()

        total = len(requests)
        hits = total - misses
        within_bounds = stats.views <= view_cache_size and (
            view_cache_bytes is None
            or stats.retained_estimated_bytes <= view_cache_bytes
        )
        return {
            "schema": BENCHMARK_SCHEMA,
            "seed": seed,
            "documents": documents,
            "sources": len({document.source_id for document in corpus}),
            "users": users,
            "queries_per_user": queries_per_user,
            "limit": limit,
            "requests": total,
            "view_cache_size": view_cache_size,
            "view_cache_bytes": view_cache_bytes,
            "retained_views": stats.views,
            "retained_estimated_bytes": stats.retained_estimated_bytes,
            "evictions": stats.evictions,
            "evicted_estimated_bytes": stats.evicted_estimated_bytes,
            "max_views": stats.max_views,
            "max_bytes": stats.max_bytes,
            "within_bounds": within_bounds,
            "hits": hits,
            "misses": misses,
            "hit_rate": round(hits / total, 6) if total else 0.0,
            "authorized_documents": {
                "min": min(authorized_counts),
                "max": max(authorized_counts),
                "mean": round(sum(authorized_counts) / len(authorized_counts), 3),
            },
            "tracemalloc": {
                "enabled": tracemalloc_enabled,
                "retained_bytes": retained,
                "peak_bytes": peak,
                "note": (
                    "Actual tracemalloc allocations made while tracing (brain, "
                    "retained views, and indexes); corpus and store rows built "
                    "before the window are not counted. Not an RSS reading."
                ),
            },
            "estimate_note": (
                "retained_estimated_bytes is the engine's explicit object-size "
                "estimate, not RSS and not a hard process-memory cap; the byte "
                "budget uses the same estimate."
            ),
            "timing_note": (
                "No machine-time threshold is applied. elapsed_seconds is "
                "informational only and varies by machine."
            ),
            "elapsed_seconds": round(elapsed, 6),
        }

    if workdir is not None:
        Path(workdir).mkdir(parents=True, exist_ok=True)
        return _execute(Path(tempfile.mkdtemp(prefix="cache-memory-", dir=workdir)))
    with tempfile.TemporaryDirectory(prefix="company-brain-cache-memory-") as path:
        return _execute(Path(path))


def _non_negative(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("value must not be negative")
    return number


def _positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return number


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--documents", type=_positive, default=DEFAULT_DOCUMENTS)
    parser.add_argument("--users", type=_positive, default=DEFAULT_USERS)
    parser.add_argument(
        "--queries-per-user", type=_positive, default=DEFAULT_QUERIES_PER_USER
    )
    parser.add_argument("--limit", type=_positive, default=DEFAULT_LIMIT)
    parser.add_argument(
        "--view-cache-size", type=_non_negative, default=DEFAULT_VIEW_CACHE_SIZE
    )
    parser.add_argument(
        "--view-cache-bytes", type=_non_negative, default=DEFAULT_VIEW_CACHE_BYTES
    )
    parser.add_argument(
        "--no-byte-budget",
        dest="byte_budget",
        action="store_false",
        default=True,
        help="disable the retained-byte budget and exercise the count bound alone",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--workdir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--no-tracemalloc",
        dest="tracemalloc",
        action="store_false",
        default=True,
        help="disable allocation tracing",
    )
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
        view_cache_size=args.view_cache_size,
        view_cache_bytes=(args.view_cache_bytes if args.byte_budget else None),
        seed=args.seed,
        tracemalloc_enabled=args.tracemalloc,
        workdir=args.workdir,
    )
    text = json.dumps(report, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
