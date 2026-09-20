"""Index growth must not evict a warm view before an oversized rejection."""

from examples.company_brains.durable.engine import CompanyBrain
from tests.test_brain6_admission import (
    HUGE,
    HUGE_QUERY,
    QUERY,
    SCOPE,
    SMALL,
    CountingStore,
    sync_full,
    view_bytes,
)


def test_oversized_index_preserves_hot_view_when_base_admission_would_evict(tmp_path):
    with CountingStore(str(tmp_path)) as store:
        sync_full(store, SCOPE, SMALL, HUGE)
        store.set_groups(SCOPE, "bulk", {"bulk"})
        small_size = view_bytes(store, user_id="alice", indexed=True)
        large_base = view_bytes(store, user_id="bulk")
        budget = large_base + small_size // 2
        assert small_size < budget < view_bytes(store, user_id="bulk", indexed=True)
        brain = CompanyBrain(store, SCOPE, view_cache_bytes=budget)
        assert brain.search(QUERY, user_id="alice") == (SMALL,)
        assert brain.search(HUGE_QUERY, user_id="bulk") == (HUGE,)
        reads = store.snapshot_reads
        assert brain.search(QUERY, user_id="alice") == (SMALL,)
        assert store.snapshot_reads == reads
