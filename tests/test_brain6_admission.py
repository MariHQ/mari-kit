"""Wave-6 admission tests: one oversized authorized view must not pollute.

Waves 3--5 memoized fully authorized views under a cheap access token and
bounded that per-brain cache by count and by an approximate retained-byte
budget.  A gap remained in *which* view the byte budget evicted.  A single
authorized corpus that is larger than the whole budget cannot ever be retained,
yet the old enforcement admitted it at the most-recently-used end and then
walked the LRU order, so it evicted every useful smaller view before finally
discarding the oversized one.  The cache ended colder than it started.

The wave-6 contract is narrow: an individual view that exceeds the byte budget
on its own is discarded *first*, before any generic LRU eviction, both when it
is first admitted and when a lazily built BM25 index later grows an already
cached view past the budget.  Everything else is deliberately unchanged:

* a hot, smaller view survives an oversized user's search and serves the next
  request without rereading live document snapshots;
* a user's obsolete view is still revoked when the token advances, even if the
  replacement view is itself oversized, so changed access never lingers stale;
* the count bound, zero budgets, scope isolation, and persisted-record
  checksum validation behave exactly as before.
"""

from __future__ import annotations

import pytest

from examples.company_brains.durable import engine as engine_module
from examples.company_brains.durable.cache_records import seal_cache_record
from examples.company_brains.durable.engine import CompanyBrain
from examples.company_brains.durable.store import SQLiteBrainStore
from mari_kit import (
    DocumentACL,
    KnowledgeDocument,
    PollPage,
    Principal,
    ScopeRef,
    SyncMode,
)
from mari_kit.json import canonical_json_bytes
from mari_kit.sync import plan_sync

SOURCE = "handbook:wave6"
SCOPE = ScopeRef(tenant="wave6", space="brain")
OTHER_SCOPE = ScopeRef(tenant="wave6", space="other")
SUPPORT = Principal(kind="team", identifier="support")
BULK = Principal(kind="team", identifier="bulk")

QUESTION = "What is the refund window?"
QUERY = "refund window"
QUOTE = "The refund window is 30 days."


def document(
    external_id: str,
    body: str,
    revision: str,
    *,
    title: str,
    visibility: str = "restricted",
    principals: tuple[Principal, ...] = (SUPPORT,),
) -> KnowledgeDocument:
    return KnowledgeDocument(
        source_id=SOURCE,
        external_id=external_id,
        title=title,
        body=body,
        revision=revision,
        acl=DocumentACL(visibility=visibility, principals=principals),
    )


SMALL = document(
    "refunds",
    QUOTE,
    "v1",
    title="Refund policy",
    visibility="public",
)


def bulk_body(tokens: int = 4000) -> str:
    """A body with many distinct terms, so its BM25 index is large."""

    return " ".join(f"token{index:05d}" for index in range(tokens))


HUGE = document(
    "bulk-memo",
    bulk_body(),
    "v1",
    title="Bulk memo",
    principals=(BULK,),
)

# A query that matches the huge, bulk-only document.
HUGE_QUERY = "token00042"


def sync_full(
    store: SQLiteBrainStore, scope: ScopeRef, *documents: KnowledgeDocument
) -> None:
    plan = plan_sync(
        store.state(scope, SOURCE),
        PollPage(upserts=tuple(documents), snapshot_complete=True),
        source_id=SOURCE,
        mode=SyncMode.FULL,
    )
    store.apply_plan(scope, plan)


class CountingStore(SQLiteBrainStore):
    """A store that records how often the engine read the live snapshot."""

    def __init__(self, path: str) -> None:
        super().__init__(path)
        self.snapshot_reads = 0
        self.token_reads = 0

    def access_token(self, scope: ScopeRef, user_id: str):  # type: ignore[no-untyped-def]
        self.token_reads += 1
        return super().access_token(scope, user_id)

    def access_token_snapshot(self, scope: ScopeRef, user_id: str):  # type: ignore[no-untyped-def]
        self.snapshot_reads += 1
        return super().access_token_snapshot(scope, user_id)


@pytest.fixture
def path(tmp_path: object) -> str:
    return str(tmp_path)


def view_bytes(
    store: SQLiteBrainStore,
    *,
    scope: ScopeRef = SCOPE,
    user_id: str,
    indexed: bool = False,
) -> int:
    """Measure one authorized view via an unbounded probe brain."""

    brain = CompanyBrain(store, scope)
    view = brain._view(user_id)
    if indexed:
        _ = view.index
    return view.estimated_bytes()


def citing_generate(target: KnowledgeDocument):
    """A host callback that cites ``target`` without touching the index."""

    def generate(question: str, documents: tuple[KnowledgeDocument, ...]):
        return {
            "answer": target.body,
            "disposition": "grounded",
            "evidence": [{"document_id": target.document_id, "quote": target.body}],
        }

    return generate


def stored_record(
    store: SQLiteBrainStore, scope: ScopeRef, key: str
) -> dict[str, object]:
    record = store.load_cache(scope, key)
    assert record is not None, "expected a persisted cache record"
    return record


# --------------------------------------------------------------------------- #
# Initial admission: a base-oversized view is discarded first
# --------------------------------------------------------------------------- #


def test_base_oversized_view_does_not_evict_hot_small_view(path: str) -> None:
    store = CountingStore(path)
    try:
        sync_full(store, SCOPE, SMALL, HUGE)
        store.set_groups(SCOPE, "alice", {"support"})
        store.set_groups(SCOPE, "bulk", {"bulk"})

        alice_indexed = view_bytes(store, user_id="alice", indexed=True)
        bulk_base = view_bytes(store, user_id="bulk")
        # ``bulk`` sees the same public document plus a body that alone exceeds
        # the whole budget, so its view can never be retained.
        assert bulk_base > alice_indexed

        brain = CompanyBrain(store, SCOPE, view_cache_bytes=alice_indexed)
        assert brain.search(QUERY, user_id="alice") == (SMALL,)
        warmed = brain._view("alice")
        assert brain.cache_stats().views == 1
        reads_before = store.snapshot_reads

        # Admitting the oversized view must drop it, not the hot small one.
        brain.search(HUGE_QUERY, user_id="bulk")
        stats = brain.cache_stats()
        assert stats.views == 1
        assert stats.retained_estimated_bytes <= alice_indexed
        assert brain._view("alice") is warmed

        # The surviving hot view answers without rereading the snapshot; the
        # only extra read is the one that built the oversized view.
        assert brain.search(QUERY, user_id="alice") == (SMALL,)
        assert store.snapshot_reads == reads_before + 1
        assert brain._view("alice") is warmed
    finally:
        store.close()


def test_oversized_view_still_serves_its_current_request(path: str) -> None:
    with SQLiteBrainStore(path) as store:
        sync_full(store, SCOPE, SMALL, HUGE)
        store.set_groups(SCOPE, "alice", {"support"})
        store.set_groups(SCOPE, "bulk", {"bulk"})
        budget = view_bytes(store, user_id="alice", indexed=True)

        brain = CompanyBrain(store, SCOPE, view_cache_bytes=budget)
        assert brain.search(HUGE_QUERY, user_id="bulk") == (HUGE,)
        assert brain.cache_stats().views == 0


# --------------------------------------------------------------------------- #
# Lazy index growth: the growing view is discarded first
# --------------------------------------------------------------------------- #


def test_lazy_index_oversize_does_not_evict_hot_small_view(path: str) -> None:
    store = CountingStore(path)
    try:
        sync_full(store, SCOPE, SMALL, HUGE)
        store.set_groups(SCOPE, "alice", {"support"})
        store.set_groups(SCOPE, "bulk", {"bulk"})

        alice_base = view_bytes(store, user_id="alice")
        bulk_base = view_bytes(store, user_id="bulk")
        bulk_indexed = view_bytes(store, user_id="bulk", indexed=True)
        # Both base views fit; the bulk view overflows only once indexed.
        budget = alice_base + bulk_base
        assert bulk_base <= budget < bulk_indexed

        brain = CompanyBrain(store, SCOPE, view_cache_bytes=budget)
        # Warm the small user with a host callback so its index is not built.
        assert (
            brain.answer(QUESTION, user_id="alice", generate=citing_generate(SMALL))[
                "disposition"
            ]
            == "grounded"
        )
        warmed = brain._view("alice")
        assert brain.cache_stats().views == 1
        reads_before = store.snapshot_reads

        # The bulk view is admitted on its base size, then its lazy index grows
        # it past the budget; it must be dropped before any LRU eviction.
        assert brain.search(HUGE_QUERY, user_id="bulk") == (HUGE,)
        stats = brain.cache_stats()
        assert stats.views == 1
        assert stats.retained_estimated_bytes <= budget
        assert brain._view("alice") is warmed

        hit = brain.answer(QUESTION, user_id="alice", generate=citing_generate(SMALL))
        assert hit["cache_hit"] is True
        assert store.snapshot_reads == reads_before + 1
        assert brain._view("alice") is warmed
    finally:
        store.close()


# --------------------------------------------------------------------------- #
# Per-user revocation is preserved even when the replacement is oversized
# --------------------------------------------------------------------------- #


def test_obsolete_view_is_revoked_even_when_replacement_is_oversized(
    path: str,
) -> None:
    with SQLiteBrainStore(path) as store:
        sync_full(store, SCOPE, SMALL, HUGE)
        store.set_groups(SCOPE, "carol", {"support"})
        carol_base = view_bytes(store, user_id="carol")

        brain = CompanyBrain(store, SCOPE, view_cache_bytes=carol_base)
        assert brain._view("carol") is not None
        assert brain.cache_stats().views == 1
        assert any(key[1] == "carol" for key in brain._views)

        # A token change makes the old view obsolete; the replacement now
        # includes the huge document and is itself too large to retain.  The
        # old view must still be revoked rather than left behind.
        store.set_groups(SCOPE, "carol", {"support", "bulk"})
        brain.search(HUGE_QUERY, user_id="carol")

        assert brain.cache_stats().views == 0
        assert not any(key[1] == "carol" for key in brain._views)


# --------------------------------------------------------------------------- #
# Existing bounds and safety behaviour are unchanged
# --------------------------------------------------------------------------- #


def test_count_bound_still_evicts_lru_for_in_budget_views(path: str) -> None:
    with SQLiteBrainStore(path) as store:
        sync_full(store, SCOPE, SMALL, HUGE)
        store.set_groups(SCOPE, "alice", {"support"})
        store.set_groups(SCOPE, "bulk", {"bulk"})

        brain = CompanyBrain(store, SCOPE, view_cache_size=1)
        assert brain.search(QUERY, user_id="alice") == (SMALL,)
        assert brain.search(HUGE_QUERY, user_id="bulk") == (HUGE,)

        stats = brain.cache_stats()
        assert stats.views == 1
        assert stats.evictions == 1
        assert any(key[1] == "bulk" for key in brain._views)
        assert not any(key[1] == "alice" for key in brain._views)


def test_zero_byte_budget_retains_nothing_but_serves(path: str) -> None:
    store = CountingStore(path)
    try:
        sync_full(store, SCOPE, SMALL, HUGE)
        store.set_groups(SCOPE, "alice", {"support"})

        brain = CompanyBrain(store, SCOPE, view_cache_bytes=0)
        assert brain.search(QUERY, user_id="alice") == (SMALL,)
        assert brain.search(QUERY, user_id="alice") == (SMALL,)

        stats = brain.cache_stats()
        assert stats.max_bytes == 0
        assert stats.views == 0
        assert stats.retained_estimated_bytes == 0
        assert store.snapshot_reads == 2
    finally:
        store.close()


def test_oversized_eviction_is_scope_isolated(path: str) -> None:
    with SQLiteBrainStore(path) as store:
        sync_full(store, SCOPE, SMALL, HUGE)
        sync_full(store, OTHER_SCOPE, SMALL, HUGE)
        store.set_groups(SCOPE, "alice", {"support"})
        store.set_groups(OTHER_SCOPE, "alice", {"support"})
        store.set_groups(SCOPE, "bulk", {"bulk"})

        other_brain = CompanyBrain(store, OTHER_SCOPE)
        assert other_brain.search(QUERY, user_id="alice") == (SMALL,)
        other_warmed = other_brain._view("alice")

        budget = view_bytes(store, scope=SCOPE, user_id="alice", indexed=True)
        brain = CompanyBrain(store, SCOPE, view_cache_bytes=budget)
        brain.search(QUERY, user_id="alice")
        brain.search(HUGE_QUERY, user_id="bulk")

        # The oversized search in one scope left the other scope's view intact.
        assert other_brain._view("alice") is other_warmed
        assert other_brain.cache_stats().views == 1


def test_persisted_record_checksum_still_guards_after_oversized_view(
    path: str,
) -> None:
    with SQLiteBrainStore(path) as store:
        sync_full(store, SCOPE, SMALL, HUGE)
        store.set_groups(SCOPE, "alice", {"support"})
        store.set_groups(SCOPE, "bulk", {"bulk"})
        budget = view_bytes(store, user_id="alice", indexed=True)

        brain = CompanyBrain(store, SCOPE, view_cache_bytes=budget)
        assert brain.answer(QUESTION, user_id="alice")["cache_hit"] is False
        key = brain._cache_key(QUESTION, "alice")

        brain.search(HUGE_QUERY, user_id="bulk")

        assert brain.answer(QUESTION, user_id="alice")["cache_hit"] is True
        record = stored_record(store, SCOPE, key)
        assert record["checksum"] == seal_cache_record(record)["checksum"]

        tampered = dict(record)
        tampered["answer"] = "Tampered prose that was never grounded."
        store.save_cache(SCOPE, key, tampered)

        reread = brain.answer(QUESTION, user_id="alice")
        assert reread["cache_hit"] is False
        assert QUOTE in reread["answer"]


def test_record_size_is_still_independent_of_oversized_corpus(path: str) -> None:
    with SQLiteBrainStore(path) as store:
        sync_full(store, SCOPE, SMALL, HUGE)
        store.set_groups(SCOPE, "alice", {"support"})
        brain = CompanyBrain(store, SCOPE)
        brain.answer(QUESTION, user_id="alice")
        key = brain._cache_key(QUESTION, "alice")
        record = stored_record(store, SCOPE, key)

        assert record["schema"] == engine_module.CACHE_SCHEMA
        digest = record["authorized_fingerprint"]
        assert isinstance(digest, str) and len(digest) == 64
        assert len(canonical_json_bytes(record)) < len(HUGE.body)
