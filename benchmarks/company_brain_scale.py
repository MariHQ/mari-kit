"""Reproducible scale benchmark for the durable company-brain host.

This standalone CLI generates deterministic synthetic company documents with
varied lengths, persists them through the durable SQLite store owned by
``examples.company_brains.durable``, and measures the reference lexical index
end to end.

For each requested corpus size it separates:

* ``commit`` -- durable ``SQLiteBrainStore.apply_plan`` transactions.
* ``cold_index_build`` -- a fresh :class:`RevisionBM25Index` over the durable
  projection.
* ``warm_lexical_query`` -- per-query reference-index search without filtering.
* ``acl_filtered_query`` -- per-query search restricted to host-authorized refs.
* ``batch_edit_commit`` / ``batch_edit_index_update`` -- durable revision
  updates and the reference-index delta refresh.
* ``batch_delete_commit`` / ``batch_delete_index_update`` -- durable tombstones
  and the reference-index delta refresh.

Every phase reports wall seconds (p50/p95), Python allocation peak, and process
RSS. Inputs and result structure are deterministic for a fixed ``--seed``;
timings are not. No external downloads or model calls are performed.

The durable store and engine are owned by sibling agents and may not exist at
first; the CLI imports them lazily and exits with a clear message when the
durable store module is still absent. Use ``--no-tracemalloc`` for untraced
wall times and ``--no-engine`` to skip the optional engine probe.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import random
import resource
import sys
import tempfile
import time
import tracemalloc
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from mari_kit import (
    DocumentACL,
    KnowledgeDocument,
    PollPage,
    Principal,
    ScopeRef,
    SyncMode,
    Tombstone,
)
from mari_kit.retrieval import (
    IndexOperation,
    RevisionBM25Index,
    RevisionIndexDelta,
)
from mari_kit.sync import plan_sync

BENCHMARK_SCHEMA = "mari-kit.company-brain-scale/1"
DEFAULT_SEED = 20240919
DEFAULT_SIZES = (200,)
DEFAULT_QUERY_COUNT = 20
DEFAULT_LIMIT = 5
DEFAULT_EDIT_FRACTION = 0.1
DEFAULT_DELETE_FRACTION = 0.05
DEFAULT_SEARCH_USER = "scale-user"
DEFAULT_SEARCH_GROUP = "support"
DEFAULT_QUESTION = "What does the policy require before approval?"

SOURCES = ("handbook", "eng-wiki", "support", "github:acme/platform", "slack")
TEAMS = ("support", "finance", "engineering", "security")

VOCABULARY = (
    "refund",
    "policy",
    "window",
    "invoice",
    "approval",
    "escalation",
    "retention",
    "security",
    "access",
    "vendor",
    "procurement",
    "onboarding",
    "orientation",
    "payroll",
    "benefits",
    "travel",
    "expense",
    "deployment",
    "rollback",
    "monitoring",
    "alert",
    "outage",
    "postmortem",
    "roadmap",
    "release",
    "migration",
    "schema",
    "backup",
    "restore",
    "encryption",
    "rotation",
    "credential",
    "runbook",
    "billing",
    "incident",
    "sla",
)

TITLES = (
    "Policy",
    "Runbook",
    "Memo",
    "FAQ",
    "Thread",
    "Guide",
    "Postmortem",
    "Charter",
)

_SENTENCE_COUNTS = (1, 1, 2, 2, 2, 3, 3, 4, 6, 9, 14)
_CONNECTORS = ("and", "for", "with", "before", "after", "during", "across")


def _stable_random(*parts: object) -> random.Random:
    """Return a generator whose stream depends only on the supplied parts."""

    payload = ":".join(str(part) for part in parts).encode()
    digest = hashlib.sha256(payload).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def _sentence(rng: random.Random) -> str:
    words = [rng.choice(VOCABULARY) for _ in range(rng.randint(5, 12))]
    position = rng.randrange(len(words))
    words.insert(position, rng.choice(_CONNECTORS))
    return " ".join(words).capitalize() + "."


def _body(rng: random.Random) -> str:
    sentences = rng.choice(_SENTENCE_COUNTS)
    return " ".join(_sentence(rng) for _ in range(sentences))


def _acl(rng: random.Random) -> DocumentACL:
    roll = rng.random()
    if roll < 0.25:
        return DocumentACL(visibility="public")
    if roll < 0.5:
        teams = rng.sample(TEAMS, rng.randint(1, 2))
        return DocumentACL(
            visibility="restricted",
            principals=tuple(Principal(kind="team", identifier=team) for team in teams),
        )
    return DocumentACL(visibility="connector_scope")


def build_documents(
    size: int, *, seed: int = DEFAULT_SEED
) -> tuple[KnowledgeDocument, ...]:
    """Build ``size`` deterministic varied-length synthetic company documents.

    Document ``i`` is generated from a per-index generator keyed by ``(seed, i)``,
    so a larger corpus shares an exact prefix with a smaller one.
    """

    if size < 1:
        raise ValueError("size must be positive")
    documents: list[KnowledgeDocument] = []
    for index in range(size):
        rng = _stable_random("document", seed, index)
        body = _body(rng)
        words = len(body.split())
        length_class = "short" if words <= 40 else "medium" if words <= 140 else "long"
        documents.append(
            KnowledgeDocument(
                source_id=SOURCES[index % len(SOURCES)],
                external_id=f"doc-{index:06d}",
                title=f"{rng.choice(VOCABULARY).title()} {rng.choice(TITLES)} {index:06d}",
                body=body,
                revision=f"v1-{index:06d}",
                metadata={
                    "index": index,
                    "seed": seed,
                    "length_class": length_class,
                    "word_count": words,
                },
                acl=_acl(rng),
            )
        )
    return tuple(documents)


def build_queries(count: int, *, seed: int = DEFAULT_SEED) -> tuple[str, ...]:
    """Build deterministic one-to-three term lexical queries."""

    if count < 1:
        raise ValueError("count must be positive")
    rng = _stable_random("queries", seed)
    return tuple(
        " ".join(rng.choice(VOCABULARY) for _ in range(rng.randint(1, 3)))
        for _ in range(count)
    )


def _select_targets(
    documents: Sequence[KnowledgeDocument], count: int
) -> tuple[KnowledgeDocument, ...]:
    ordered = sorted(documents, key=lambda document: document.document_id)
    count = min(count, len(ordered))
    if count <= 0:
        return ()
    step = max(1, len(ordered) // count)
    return tuple(ordered[::step][:count])


def build_edits(
    documents: Sequence[KnowledgeDocument],
    *,
    count: int,
    seed: int = DEFAULT_SEED,
) -> tuple[KnowledgeDocument, ...]:
    """Build replacement revisions for a deterministic subset of documents."""

    if count < 0:
        raise ValueError("count must not be negative")
    edits: list[KnowledgeDocument] = []
    for position, document in enumerate(_select_targets(documents, count)):
        rng = _stable_random("edit", seed, document.document_id)
        edits.append(
            replace(
                document,
                body=f"{document.body} {_sentence(rng)}",
                revision=f"{document.revision}.edit-{position:04d}",
                content_digest="",
            )
        )
    return tuple(edits)


def build_deletions(
    documents: Sequence[KnowledgeDocument], *, count: int
) -> tuple[Tombstone, ...]:
    """Build deterministic tombstones for a subset of documents."""

    if count < 0:
        raise ValueError("count must not be negative")
    return tuple(
        Tombstone(source_id=document.source_id, external_id=document.external_id)
        for document in _select_targets(documents, count)
    )


def host_allowed_refs(
    documents: Iterable[KnowledgeDocument],
    *,
    groups: Iterable[str],
    user_id: str,
    scope: ScopeRef,
):
    """Host policy mirror of the durable engine: open docs plus group/user ACLs."""

    principals = {Principal(kind="team", identifier=group) for group in groups}
    principals.add(Principal(kind="user", identifier=user_id))
    return frozenset(
        document.ref_in(scope)
        for document in documents
        if document.acl.visibility in {"public", "connector_scope"}
        or principals.intersection(document.acl.principals)
    )


def percentile(ordered: Sequence[float], fraction: float) -> float:
    """Nearest-rank percentile over an already sorted sequence."""

    if not ordered:
        raise ValueError("percentile requires at least one sample")
    if not 0.0 <= fraction <= 1.0:
        raise ValueError("fraction must be between zero and one")
    rank = max(1, math.ceil(fraction * len(ordered)))
    return float(ordered[rank - 1])


def latency_summary(values: Sequence[float]) -> dict:
    """Summarize wall samples in seconds with explicit units in every key."""

    data = sorted(float(value) for value in values)
    if not data:
        raise ValueError("latency summary requires at least one sample")
    total = sum(data)
    return {
        "unit": "seconds",
        "count": len(data),
        "latency_kind": "single_shot" if len(data) == 1 else "sampled",
        "p95_valid": len(data) >= 20,
        "total_seconds": round(total, 6),
        "mean_seconds": round(total / len(data), 6),
        "min_seconds": round(data[0], 6),
        "p50_seconds": round(percentile(data, 0.5), 6),
        "p95_seconds": round(percentile(data, 0.95), 6),
        "max_seconds": round(data[-1], 6),
    }


def process_rss_bytes() -> int:
    """Return the process RSS high-water mark normalized to bytes.

    ``ru_maxrss`` is bytes on macOS and kilobytes elsewhere; both are converted
    to a single byte unit for comparison.
    """

    maxrss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(maxrss) if sys.platform == "darwin" else int(maxrss) * 1024


@dataclass
class Recorder:
    """Context manager capturing wall time, allocation peak, and RSS per phase."""

    tracemalloc_enabled: bool = True

    def __post_init__(self) -> None:
        self.samples: list[float] = []

    def __enter__(self) -> Recorder:
        gc.collect()
        self.wall_seconds = 0.0
        self.allocations_peak_bytes = 0
        self.rss_before_bytes = process_rss_bytes()
        if self.tracemalloc_enabled:
            tracemalloc.start()
        self._started = time.perf_counter()
        return self

    def __exit__(self, *exc: object) -> bool:
        self.wall_seconds = time.perf_counter() - self._started
        if self.tracemalloc_enabled:
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            self.allocations_peak_bytes = peak
        self.rss_after_bytes = process_rss_bytes()
        return False

    def sample(self, seconds: float) -> None:
        self.samples.append(seconds)

    def to_dict(self) -> dict:
        return {
            "wall_seconds": round(self.wall_seconds, 6),
            "allocations_peak_bytes": self.allocations_peak_bytes,
            "process_rss_before_bytes": self.rss_before_bytes,
            "process_rss_after_bytes": self.rss_after_bytes,
            "rss_semantics": "process-lifetime peak at phase boundaries; not allocation deltas",
            "latency": latency_summary(self.samples or [self.wall_seconds]),
        }


def _group_by_source(
    documents: Iterable[KnowledgeDocument],
) -> tuple[tuple[str, tuple[KnowledgeDocument, ...]], ...]:
    grouped: dict[str, list[KnowledgeDocument]] = {}
    for document in documents:
        grouped.setdefault(document.source_id, []).append(document)
    return tuple((source, tuple(grouped[source])) for source in sorted(grouped))


def _group_tombstones(
    tombstones: Iterable[Tombstone],
) -> tuple[tuple[str, tuple[Tombstone, ...]], ...]:
    grouped: dict[str, list[Tombstone]] = {}
    for tombstone in tombstones:
        grouped.setdefault(tombstone.source_id, []).append(tombstone)
    return tuple((source, tuple(grouped[source])) for source in sorted(grouped))


def _plan(
    store,
    scope: ScopeRef,
    source: str,
    upserts: Sequence[KnowledgeDocument],
    tombstones: Sequence[Tombstone],
    *,
    mode: SyncMode,
):
    return plan_sync(
        store.state(scope, source),
        PollPage(
            upserts=tuple(upserts),
            tombstones=tuple(tombstones),
            snapshot_complete=True,
        ),
        source_id=source,
        mode=mode,
    )


def _index_units(store, scope: ScopeRef) -> dict:
    projection = store.projection(scope)
    refs = {
        document.document_id: document.ref_in(scope)
        for document in store.documents(scope)
    }
    return {refs[document_id]: body for document_id, body in projection.items()}


def durable_available() -> bool:
    """Return ``True`` when the sibling durable store module is importable."""

    try:
        import examples.company_brains.durable.store  # noqa: F401
    except Exception:
        return False
    return True


def engine_available() -> bool:
    try:
        import examples.company_brains.durable.engine  # noqa: F401
    except Exception:
        return False
    return True


def run_size(
    size: int,
    *,
    seed: int = DEFAULT_SEED,
    query_count: int = DEFAULT_QUERY_COUNT,
    limit: int = DEFAULT_LIMIT,
    edit_fraction: float = DEFAULT_EDIT_FRACTION,
    delete_fraction: float = DEFAULT_DELETE_FRACTION,
    tracemalloc_enabled: bool = True,
    engine_probe: bool = False,
    workdir: str | Path,
) -> dict:
    """Run one corpus size and return counts plus per-phase measurements."""

    from examples.company_brains.durable.store import SQLiteBrainStore

    if size < 1:
        raise ValueError("size must be positive")
    scope = ScopeRef(tenant="scale", space="company")
    documents = build_documents(size, seed=seed)
    queries = build_queries(query_count, seed=seed)
    if not 0 <= edit_fraction < 1 or not 0 <= delete_fraction < 1:
        raise ValueError("edit and delete fractions must be in [0, 1)")
    edit_count = min(size, max(1, int(size * edit_fraction))) if edit_fraction else 0
    delete_count = (
        min(size, max(1, int(size * delete_fraction))) if delete_fraction else 0
    )
    Path(workdir).mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix=f"size-{size}-", dir=workdir))
    database = directory / "brain.sqlite"

    phases: dict[str, dict] = {}
    counts: dict[str, int] = {}
    engine_result: dict = {}

    with SQLiteBrainStore(database) as store:
        grouped = _group_by_source(documents)

        with Recorder(tracemalloc_enabled) as recorder:
            for source, source_documents in grouped:
                plan = _plan(
                    store, scope, source, source_documents, (), mode=SyncMode.FULL
                )
                started = time.perf_counter()
                store.apply_plan(scope, plan)
                recorder.sample(time.perf_counter() - started)
        phases["commit"] = recorder.to_dict()
        counts["commit_plans"] = len(grouped)
        counts["commit_documents"] = len(documents)

        live = store.documents(scope)
        projection = store.projection(scope)
        units = _index_units(store, scope)
        counts["live_documents"] = len(live)
        counts["projection_documents"] = len(projection)
        counts["cold_index_units"] = len(units)
        counts["sync_manifest_entries"] = sum(
            len(store.state(scope, source).manifest) for source, _ in grouped
        )

        with Recorder(tracemalloc_enabled) as recorder:
            index = RevisionBM25Index(units)
        phases["cold_index_build"] = recorder.to_dict()

        positive_queries = 0
        positive_hits = 0
        with Recorder(tracemalloc_enabled) as recorder:
            for query in queries:
                started = time.perf_counter()
                hits = index.search(query, limit=limit)
                recorder.sample(time.perf_counter() - started)
                positive_queries += any(hit.score > 0 for hit in hits)
                positive_hits += sum(hit.score > 0 for hit in hits)
        phases["reference_index_query"] = recorder.to_dict()
        counts["queries_with_positive_hits"] = positive_queries
        counts["positive_hits"] = positive_hits

        store.set_groups(scope, DEFAULT_SEARCH_USER, (DEFAULT_SEARCH_GROUP,))
        snapshot, groups = store.access_snapshot(scope, DEFAULT_SEARCH_USER)
        allowed = host_allowed_refs(
            snapshot,
            groups=groups,
            user_id=DEFAULT_SEARCH_USER,
            scope=scope,
        )
        counts["authorized_refs"] = len(allowed)
        counts["total_refs"] = len(units)

        with Recorder(tracemalloc_enabled) as recorder:
            for query in queries:
                started = time.perf_counter()
                index.search(query, limit=limit, allowed_refs=allowed)
                recorder.sample(time.perf_counter() - started)
        phases["acl_filtered_query"] = recorder.to_dict()

        # Separate sparse reference allowlists from the host-policy point above.
        ordered_refs = sorted(units, key=lambda ref: ref.key)
        allowlist_sweep = []
        for fraction in (0.01, 0.1, 1.0):
            subset = set(ordered_refs[: max(1, int(size * fraction))])
            with Recorder(tracemalloc_enabled) as recorder:
                for query in queries:
                    started = time.perf_counter()
                    index.search(query, limit=limit, allowed_refs=subset)
                    recorder.sample(time.perf_counter() - started)
            allowlist_sweep.append(
                {
                    "authorized_refs": len(subset),
                    "total_refs": len(units),
                    "measurement": recorder.to_dict(),
                }
            )

        prior_refs = {document.document_id: document.ref_in(scope) for document in live}
        edits = build_edits(live, count=edit_count, seed=seed)
        with Recorder(tracemalloc_enabled) as recorder:
            for source, source_edits in _group_by_source(edits):
                plan = _plan(
                    store, scope, source, source_edits, (), mode=SyncMode.INCREMENTAL
                )
                started = time.perf_counter()
                store.apply_plan(scope, plan)
                recorder.sample(time.perf_counter() - started)
        phases["batch_edit_commit"] = recorder.to_dict()
        counts["edit_documents"] = len(edits)

        edit_deltas = [
            RevisionIndexDelta(
                ref=edit.ref_in(scope),
                previous_ref=prior_refs[edit.document_id],
                operation=IndexOperation.UPSERT,
                text=edit.body,
            )
            for edit in edits
        ]
        with Recorder(tracemalloc_enabled) as recorder:
            index = index.with_deltas(edit_deltas)
        phases["batch_edit_index_update"] = recorder.to_dict()

        current = store.documents(scope)
        current_refs = {
            document.document_id: document.ref_in(scope) for document in current
        }
        deletions = build_deletions(current, count=delete_count)
        with Recorder(tracemalloc_enabled) as recorder:
            for source, source_tombstones in _group_tombstones(deletions):
                plan = _plan(
                    store,
                    scope,
                    source,
                    (),
                    source_tombstones,
                    mode=SyncMode.INCREMENTAL,
                )
                started = time.perf_counter()
                store.apply_plan(scope, plan)
                recorder.sample(time.perf_counter() - started)
        phases["batch_delete_commit"] = recorder.to_dict()
        counts["delete_documents"] = len(deletions)

        delete_deltas = [
            RevisionIndexDelta(
                ref=current_refs[tombstone.document_id],
                operation=IndexOperation.DELETE,
            )
            for tombstone in deletions
        ]
        with Recorder(tracemalloc_enabled) as recorder:
            index = index.with_deltas(delete_deltas)
        phases["batch_delete_index_update"] = recorder.to_dict()

        counts["final_live_documents"] = len(store.documents(scope))

        if engine_probe and engine_available():
            from examples.company_brains.durable.engine import CompanyBrain

            store.set_groups(scope, DEFAULT_SEARCH_USER, (DEFAULT_SEARCH_GROUP,))
            brain = CompanyBrain(store, scope)
            try:
                with Recorder(tracemalloc_enabled) as recorder:
                    brain.search(queries[0], user_id=DEFAULT_SEARCH_USER, limit=limit)
                phases["engine_search"] = recorder.to_dict()
                with Recorder(tracemalloc_enabled) as recorder:
                    for query in queries:
                        started = time.perf_counter()
                        brain.search(query, user_id=DEFAULT_SEARCH_USER, limit=limit)
                        recorder.sample(time.perf_counter() - started)
                phases["engine_search_repeated"] = recorder.to_dict()
                with Recorder(tracemalloc_enabled) as recorder:
                    store.access_snapshot(scope, DEFAULT_SEARCH_USER)
                phases["store_access_snapshot"] = recorder.to_dict()
                with Recorder(tracemalloc_enabled) as recorder:
                    answer = brain.answer(DEFAULT_QUESTION, user_id=DEFAULT_SEARCH_USER)
                phases["engine_answer"] = recorder.to_dict()
                with Recorder(tracemalloc_enabled) as recorder:
                    for _ in queries:
                        started = time.perf_counter()
                        cached = brain.answer(
                            DEFAULT_QUESTION, user_id=DEFAULT_SEARCH_USER
                        )
                        recorder.sample(time.perf_counter() - started)
                        if not cached["cache_hit"]:
                            raise ValueError(
                                "cached-answer benchmark did not hit the cache"
                            )
                phases["engine_answer_cached"] = recorder.to_dict()
                engine_result = {
                    "probed": True,
                    "disposition": answer.get("disposition", ""),
                    "evidence_count": len(answer.get("evidence", [])),
                }
            except Exception as error:  # noqa: BLE001 - surface integration defect
                engine_result = {
                    "probed": True,
                    "error": f"{type(error).__name__}: {error}",
                }
        else:
            engine_result = {
                "probed": False,
                "reason": "engine unavailable or disabled",
            }

        final_projection = store.projection(scope)

    storage_bytes = {
        suffix or "main": Path(str(database) + suffix).stat().st_size
        if Path(str(database) + suffix).exists()
        else 0
        for suffix in ("", "-wal", "-shm")
    }
    database_bytes = sum(storage_bytes.values())
    result = {
        "size": size,
        "seed": seed,
        "documents": len(documents),
        "sources": len({document.source_id for document in documents}),
        "queries": len(queries),
        "limit": limit,
        "counts": counts,
        "phases": phases,
        "engine": engine_result,
        "database_bytes": database_bytes,
        "storage_bytes": storage_bytes,
        "reference_allowlist_sweep": allowlist_sweep,
        "final_projection_documents": len(final_projection),
        "process_rss_peak_bytes": process_rss_bytes(),
    }
    if counts["final_live_documents"] != len(final_projection):
        result["consistency_warning"] = (
            "live document count does not match durable projection size"
        )
    return result


def run(
    sizes: Sequence[int] = DEFAULT_SIZES,
    *,
    seed: int = DEFAULT_SEED,
    query_count: int = DEFAULT_QUERY_COUNT,
    limit: int = DEFAULT_LIMIT,
    edit_fraction: float = DEFAULT_EDIT_FRACTION,
    delete_fraction: float = DEFAULT_DELETE_FRACTION,
    tracemalloc_enabled: bool = True,
    engine_probe: bool = False,
    workdir: str | Path | None = None,
) -> dict:
    """Run every size and return the full JSON-serializable report."""

    if not sizes:
        raise ValueError("at least one size is required")
    if not durable_available():
        raise RuntimeError(
            "durable store is not importable yet: examples.company_brains.durable.store"
        )

    def _execute(directory: Path) -> dict:
        size_results = [
            run_size(
                int(size),
                seed=seed,
                query_count=query_count,
                limit=limit,
                edit_fraction=edit_fraction,
                delete_fraction=delete_fraction,
                tracemalloc_enabled=tracemalloc_enabled,
                engine_probe=engine_probe,
                workdir=directory,
            )
            for size in sizes
        ]
        return {
            "schema": BENCHMARK_SCHEMA,
            "seed": seed,
            "query_count": query_count,
            "sizes_requested": [int(size) for size in sizes],
            "scope": {"tenant": "scale", "space": "company"},
            "engine_available": engine_available(),
            "timing_note": (
                "Inputs are deterministic for a fixed seed; wall seconds are not. "
                "tracemalloc overhead is included unless --no-tracemalloc."
            ),
            "memory_note": (
                "process_rss bytes are the ru_maxrss high-water mark normalized "
                "to bytes (macOS bytes, other platforms KB*1024)."
            ),
            "reference_index_note": (
                "RevisionBM25Index rebuilds corpus statistics on every with_deltas; "
                "batch index update times include a full rebuild. "
                "reference_index_query times a prebuilt index. The actual engine "
                "checks live access tokens and reuses authorized snapshots and indexes "
                "when unchanged; engine_search_repeated measures that warm path. "
                "Commit phase wall_seconds includes planning; its latency samples "
                "measure source-plan commits only. Each update serializes the full source manifest."
            ),
            "results": size_results,
        }

    if workdir is not None:
        return _execute(Path(workdir))
    with tempfile.TemporaryDirectory(prefix="company-brain-scale-") as directory:
        return _execute(Path(directory))


def _positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return number


def _fraction(value: str) -> float:
    number = float(value)
    if not 0.0 <= number < 1.0:
        raise argparse.ArgumentTypeError("fraction must be in [0, 1)")
    return number


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sizes",
        type=_positive_int,
        nargs="+",
        default=list(DEFAULT_SIZES),
        help="corpus sizes to benchmark (default: %(default)s)",
    )
    parser.add_argument("--output", type=Path, help="write the JSON report here")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--queries", type=_positive_int, default=DEFAULT_QUERY_COUNT)
    parser.add_argument("--limit", type=_positive_int, default=DEFAULT_LIMIT)
    parser.add_argument(
        "--edit-fraction", type=_fraction, default=DEFAULT_EDIT_FRACTION
    )
    parser.add_argument(
        "--delete-fraction", type=_fraction, default=DEFAULT_DELETE_FRACTION
    )
    parser.add_argument("--workdir", type=Path)
    parser.add_argument(
        "--no-tracemalloc",
        dest="tracemalloc",
        action="store_false",
        default=True,
        help="disable allocation tracing for lower-overhead wall times",
    )
    parser.add_argument(
        "--no-engine",
        dest="engine",
        action="store_false",
        default=True,
        help="skip the optional durable engine probe",
    )
    args = parser.parse_args(argv)

    report = run(
        args.sizes,
        seed=args.seed,
        query_count=args.queries,
        limit=args.limit,
        edit_fraction=args.edit_fraction,
        delete_fraction=args.delete_fraction,
        tracemalloc_enabled=args.tracemalloc,
        engine_probe=args.engine,
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
