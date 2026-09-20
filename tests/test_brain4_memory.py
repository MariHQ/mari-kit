"""Wave-4 memory-bound tests for the durable company brain view cache.

Wave 3 bounded the authorized-view cache by *count* only, so a brain serving
many users could still pin an unbounded amount of document text as long as the
number of cached views stayed below the bound.  These tests pin the wave-4
byte-bound contract on top of the existing count bound:

* ``view_cache_bytes`` configures an approximate retained-byte budget; it is
  validated (no booleans, no negatives) and defaults to ``None`` so the wave-3
  constructor contract is unchanged;
* the byte budget is enforced both when a view is stored and again when the
  lazily built BM25 index grows a view that is already cached;
* a view larger than the budget may still serve the current request but must
  not stay cached;
* changing a user's access token evicts that user's obsolete views instead of
  letting edit history accumulate;
* ``cache_stats`` exposes read-only retained estimated bytes, view count, and
  eviction accounting, and documents that the bytes are an estimate rather than
  an RSS hard cap;
* a zero count or byte budget retains nothing while still answering correctly.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from examples.company_brains.durable import engine as engine_module
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
from mari_kit.retrieval import RevisionBM25Index
from mari_kit.sync import plan_sync

SOURCE = "handbook:wave4"
SCOPE = ScopeRef(tenant="wave4", space="brain")
SUPPORT = Principal(kind="team", identifier="support")
FINANCE = Principal(kind="team", identifier="finance")
QUESTION = "What is the refund window?"
OTHER_QUESTION = "How long is the refund window?"
QUERY = "refund window"

DEFAULT_VIEW_CACHE_SIZE = engine_module._DEFAULT_VIEW_CACHE_SIZE


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


POLICY = document(
    "refunds", "The refund window is 30 days.", "v1", title="Refund policy"
)
PUBLIC = document(
    "orientation",
    "New employees attend orientation on Monday.",
    "v1",
    title="Onboarding",
    visibility="public",
)
BUDGET = document(
    "budget", "The travel budget is 500 dollars.", "v1", title="Travel budget"
)

QUOTE = "The refund window is 30 days."


def sync_full(store: SQLiteBrainStore, *documents: KnowledgeDocument) -> None:
    plan = plan_sync(
        store.state(SCOPE, SOURCE),
        PollPage(upserts=tuple(documents), snapshot_complete=True),
        source_id=SOURCE,
        mode=SyncMode.FULL,
    )
    store.apply_plan(SCOPE, plan)


class CountingStore(SQLiteBrainStore):
    """A store that records how often the engine rebuilt an authorized view."""

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


class _CountingIndex(RevisionBM25Index):
    builds = 0

    def __init__(self, *args: object, **kwargs: object) -> None:
        type(self).builds += 1
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]


@pytest.fixture
def path(tmp_path: object) -> str:
    return str(tmp_path)


def callback_generate(
    question: str, documents: tuple[KnowledgeDocument, ...]
) -> dict[str, object]:
    """A host callback that never touches the extractive BM25 index."""

    return {
        "answer": QUOTE,
        "disposition": "grounded",
        "evidence": [{"document_id": POLICY.document_id, "quote": QUOTE}],
    }


def probe_view_bytes(store: SQLiteBrainStore, *, user_id: str = "alice") -> int:
    """Measure one fully indexed authorized view via a default-budget brain."""

    brain = CompanyBrain(store, SCOPE)
    brain.search(QUERY, user_id=user_id)
    stats = brain.cache_stats()
    assert stats.views == 1
    assert stats.retained_estimated_bytes > 0
    return stats.retained_estimated_bytes


def test_constructor_defaults_preserve_count_only_cache(path: str) -> None:
    with SQLiteBrainStore(path) as store:
        sync_full(store, PUBLIC, POLICY)
        store.set_groups(SCOPE, "alice", {"support"})
        brain = CompanyBrain(store, SCOPE)

        initial = brain.cache_stats()
        assert initial.views == 0
        assert initial.retained_estimated_bytes == 0
        assert initial.evictions == 0
        assert initial.max_views == DEFAULT_VIEW_CACHE_SIZE
        assert initial.max_bytes is None

        assert brain.search(QUERY, user_id="alice") == (POLICY,)
        warmed = brain.cache_stats()
        assert warmed.views == 1
        assert warmed.retained_estimated_bytes > 0
        assert warmed.max_bytes is None


def test_bool_budgets_are_rejected(path: str) -> None:
    with SQLiteBrainStore(path) as store:
        for value in (True, False):
            with pytest.raises(TypeError):
                CompanyBrain(store, SCOPE, view_cache_size=value)
            with pytest.raises(TypeError):
                CompanyBrain(store, SCOPE, view_cache_bytes=value)


def test_negative_budgets_are_rejected(path: str) -> None:
    with SQLiteBrainStore(path) as store:
        with pytest.raises(ValueError):
            CompanyBrain(store, SCOPE, view_cache_size=-1)
        with pytest.raises(ValueError):
            CompanyBrain(store, SCOPE, view_cache_bytes=-1)


def test_non_integer_budgets_are_rejected(path: str) -> None:
    with SQLiteBrainStore(path) as store:
        with pytest.raises(TypeError):
            CompanyBrain(store, SCOPE, view_cache_size="8")
        with pytest.raises(TypeError):
            CompanyBrain(store, SCOPE, view_cache_bytes=1.5)
        with pytest.raises(TypeError):
            CompanyBrain(store, SCOPE, view_cache_size=None)


def test_zero_budgets_are_accepted(path: str) -> None:
    with SQLiteBrainStore(path) as store:
        brain = CompanyBrain(store, SCOPE, view_cache_size=0, view_cache_bytes=0)
        assert brain.cache_stats().max_views == 0
        assert brain.cache_stats().max_bytes == 0


def test_count_bound_evicts_least_recently_used(path: str) -> None:
    with SQLiteBrainStore(path) as store:
        sync_full(store, PUBLIC, POLICY)
        store.set_groups(SCOPE, "alice", {"support"})
        store.set_groups(SCOPE, "bob", {"finance"})
        brain = CompanyBrain(store, SCOPE, view_cache_size=1)

        assert brain.search(QUERY, user_id="alice") == (POLICY,)
        assert brain.search(QUERY, user_id="bob") == ()
        assert brain.search(QUERY, user_id="alice") == (POLICY,)

        stats = brain.cache_stats()
        assert stats.views == 1
        assert stats.max_views == 1
        assert stats.evictions == 2
        assert stats.evicted_estimated_bytes > 0


def test_byte_budget_evicts_until_under_budget(path: str) -> None:
    with SQLiteBrainStore(path) as store:
        sync_full(store, PUBLIC, POLICY)
        store.set_groups(SCOPE, "alice", {"support"})
        store.set_groups(SCOPE, "bob", {"finance"})
        unit = probe_view_bytes(store)

        brain = CompanyBrain(store, SCOPE, view_cache_bytes=unit)
        assert brain.search(QUERY, user_id="alice") == (POLICY,)
        assert brain.cache_stats().retained_estimated_bytes <= unit

        # Bob's smaller view pushes the total over the budget and evicts Alice.
        assert brain.search(QUERY, user_id="bob") == ()
        stats = brain.cache_stats()
        assert stats.retained_estimated_bytes <= unit
        assert stats.evictions >= 1
        assert stats.views == 1


def test_lazy_index_build_triggers_byte_enforcement(path: str) -> None:
    store = CountingStore(path)
    try:
        sync_full(store, PUBLIC, POLICY)
        store.set_groups(SCOPE, "alice", {"support"})

        probe = CompanyBrain(store, SCOPE)
        assert (
            probe.answer(QUESTION, user_id="alice", generate=callback_generate)[
                "disposition"
            ]
            == "grounded"
        )
        base = probe.cache_stats().retained_estimated_bytes
        assert probe.cache_stats().views == 1
        assert base > 0

        # Budget fits the documents but not the lazily built index.
        bounded = CompanyBrain(store, SCOPE, view_cache_bytes=base)
        assert (
            bounded.answer(OTHER_QUESTION, user_id="alice", generate=callback_generate)[
                "disposition"
            ]
            == "grounded"
        )
        cached_only = bounded.cache_stats()
        assert cached_only.views == 1
        assert cached_only.retained_estimated_bytes == base

        # Building the index grows the already-cached view past the budget, so
        # the budget is re-enforced and the view is dropped after serving.
        assert bounded.search(QUERY, user_id="alice") == (POLICY,)
        after_index = bounded.cache_stats()
        assert after_index.views == 0
        assert after_index.retained_estimated_bytes == 0
        assert after_index.evictions >= 1
    finally:
        store.close()


def test_oversized_view_serves_request_but_is_not_retained(path: str) -> None:
    with SQLiteBrainStore(path) as store:
        sync_full(store, PUBLIC, POLICY)
        store.set_groups(SCOPE, "alice", {"support"})
        unit = probe_view_bytes(store)
        assert unit > 1

        tiny = CompanyBrain(store, SCOPE, view_cache_bytes=unit // 2)
        assert tiny.search(QUERY, user_id="alice") == (POLICY,)
        stats = tiny.cache_stats()
        assert stats.views == 0
        assert stats.retained_estimated_bytes == 0
        assert stats.evictions >= 1


def test_zero_byte_budget_retains_nothing_but_serves(path: str) -> None:
    with SQLiteBrainStore(path) as store:
        sync_full(store, PUBLIC, POLICY)
        store.set_groups(SCOPE, "alice", {"support"})
        brain = CompanyBrain(store, SCOPE, view_cache_bytes=0)

        assert brain.search(QUERY, user_id="alice") == (POLICY,)
        assert brain.search(QUERY, user_id="alice") == (POLICY,)
        assert brain.answer(QUESTION, user_id="alice")["disposition"] == "grounded"

        stats = brain.cache_stats()
        assert stats.max_bytes == 0
        assert stats.views == 0
        assert stats.retained_estimated_bytes == 0
        assert stats.evictions >= 3


def test_zero_count_budget_retains_nothing_but_serves(path: str) -> None:
    with SQLiteBrainStore(path) as store:
        sync_full(store, PUBLIC, POLICY)
        store.set_groups(SCOPE, "alice", {"support"})
        brain = CompanyBrain(store, SCOPE, view_cache_size=0)

        assert brain.search(QUERY, user_id="alice") == (POLICY,)
        assert brain.search(QUERY, user_id="alice") == (POLICY,)

        stats = brain.cache_stats()
        assert stats.max_views == 0
        assert stats.views == 0
        assert stats.retained_estimated_bytes == 0
        assert stats.evictions >= 2


def test_token_change_evicts_obsolete_view_for_same_user(path: str) -> None:
    with SQLiteBrainStore(path) as store:
        sync_full(store, PUBLIC, POLICY)
        store.set_groups(SCOPE, "alice", {"support"})
        brain = CompanyBrain(store, SCOPE)

        assert brain.search(QUERY, user_id="alice") == (POLICY,)
        first = brain.cache_stats()
        assert first.views == 1
        assert first.evictions == 0
        authorized_bytes = first.retained_estimated_bytes

        store.set_groups(SCOPE, "alice", set())
        assert brain.search(QUERY, user_id="alice") == ()
        revoked = brain.cache_stats()
        assert revoked.views == 1
        assert revoked.evictions == 1
        assert revoked.retained_estimated_bytes < authorized_bytes

        store.set_groups(SCOPE, "alice", {"support"})
        assert brain.search(QUERY, user_id="alice") == (POLICY,)
        restored = brain.cache_stats()
        assert restored.views == 1
        assert restored.evictions == 2


def test_byte_budget_holds_across_invalidation(path: str) -> None:
    with SQLiteBrainStore(path) as store:
        sync_full(store, PUBLIC, POLICY)
        store.set_groups(SCOPE, "alice", {"support"})
        unit = probe_view_bytes(store)

        brain = CompanyBrain(store, SCOPE, view_cache_bytes=unit)
        assert brain.search(QUERY, user_id="alice") == (POLICY,)
        assert brain.cache_stats().retained_estimated_bytes <= unit

        store.set_groups(SCOPE, "alice", set())
        assert brain.search(QUERY, user_id="alice") == ()
        stats = brain.cache_stats()
        assert stats.retained_estimated_bytes <= unit
        assert stats.views == 1
        assert stats.evictions == 1


def test_lazy_index_is_reused_under_byte_budget(
    path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(engine_module, "RevisionBM25Index", _CountingIndex)
    with SQLiteBrainStore(path) as store:
        sync_full(store, PUBLIC, POLICY)
        store.set_groups(SCOPE, "alice", {"support"})

        measuring = CompanyBrain(store, SCOPE)
        measuring.search(QUERY, user_id="alice")
        unit = measuring.cache_stats().retained_estimated_bytes
        baseline_builds = _CountingIndex.builds

        brain = CompanyBrain(store, SCOPE, view_cache_bytes=unit)
        assert brain.search(QUERY, user_id="alice") == (POLICY,)
        assert _CountingIndex.builds == baseline_builds + 1
        assert brain.search(QUERY, user_id="alice") == (POLICY,)
        assert _CountingIndex.builds == baseline_builds + 1

        stats = brain.cache_stats()
        assert stats.views == 1
        assert stats.evictions == 0


def test_view_does_not_store_a_duplicate_by_id_mapping() -> None:
    slots = engine_module._AuthorizedView.__slots__
    assert "documents" in slots
    assert "refs" in slots
    assert "by_id" not in slots


def test_cache_stats_is_a_read_only_snapshot(path: str) -> None:
    with SQLiteBrainStore(path) as store:
        sync_full(store, PUBLIC, POLICY)
        store.set_groups(SCOPE, "alice", {"support"})
        brain = CompanyBrain(store, SCOPE)
        brain.search(QUERY, user_id="alice")

        stats = brain.cache_stats()
        assert stats.retained_estimated_bytes > 0
        with pytest.raises(FrozenInstanceError):
            stats.views = 99  # type: ignore[misc]

        # The returned value is a snapshot: later activity does not mutate it.
        store.set_groups(SCOPE, "alice", set())
        brain.search(QUERY, user_id="alice")
        assert stats.views == 1
        assert brain.cache_stats().evictions == 1
