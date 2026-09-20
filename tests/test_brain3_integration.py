"""Independent checks of warm reads and transactional invalidation."""

from dataclasses import replace

import numpy as np
import pytest

from examples.company_brains.durable.engine import CompanyBrain
from examples.company_brains.durable.store import SQLiteBrainStore
from mari_kit.retrieval import DenseFlatIndex, HNSWIndex
from tests.test_brain2_integration import SCOPE, apply, doc, prediction


def test_reusing_brain_with_another_scope_never_reuses_old_view(tmp_path):
    from mari_kit import PollPage, ScopeRef, SyncMode
    from mari_kit.sync import plan_sync

    other = ScopeRef(tenant="other")
    with SQLiteBrainStore(tmp_path / "brain.sqlite") as store:
        original = doc()
        alternate = doc(body="Refunds are available for 75 days.")
        apply(store, original)
        step = plan_sync(
            store.state(other, "handbook"),
            PollPage(upserts=(alternate,), snapshot_complete=True),
            source_id="handbook",
            mode=SyncMode.INCREMENTAL,
        )
        store.apply_plan(other, step)
        brain = CompanyBrain(store, SCOPE)
        assert brain.search("refund", user_id="alice") == (original,)
        brain.scope = other
        assert brain.search("refund", user_id="alice") == (alternate,)


@pytest.mark.parametrize("metric", ["cosine", "dot", "l2"])
def test_fallback_preserves_exact_scores_for_original_query(metric):
    rng = np.random.default_rng(81)
    vectors = {str(i): rng.normal(size=7) for i in range(20)}
    query = rng.normal(size=7)
    allowed = {"1", "4", "12"}
    expected = DenseFlatIndex(vectors, metric=metric).search(
        query, limit=3, allowed_document_ids=allowed
    )
    actual = HNSWIndex(vectors, metric=metric).search(
        query, limit=3, allowed_document_ids=allowed, exact_filter_threshold=3
    )
    assert actual == expected


def test_warm_requests_do_not_reload_document_payloads(tmp_path):
    with SQLiteBrainStore(tmp_path / "brain.sqlite") as store:
        policy = doc()
        apply(store, policy)
        brain = CompanyBrain(store, SCOPE)
        brain.answer(
            "Refund window?", user_id="alice", generate=lambda *_: prediction(policy)
        )
        brain.search("refund", user_id="alice")
        statements = []
        store._connection.set_trace_callback(statements.append)
        assert brain.answer("Refund window?", user_id="alice")["cache_hit"]
        assert brain.search("refund", user_id="alice") == (policy,)
        reads = [
            sql.lower()
            for sql in statements
            if sql.lstrip().lower().startswith("select")
        ]
        assert reads, "Warm requests must still check live access state"
        assert not any("from documents" in sql and "payload" in sql for sql in reads)


def test_rolled_back_edit_preserves_cache_then_committed_edit_invalidates(tmp_path):
    path = tmp_path / "brain.sqlite"
    with SQLiteBrainStore(path) as reader, SQLiteBrainStore(path) as writer:
        policy = doc()
        apply(writer, policy)
        brain = CompanyBrain(reader, SCOPE)
        brain.answer(
            "Refund window?", user_id="alice", generate=lambda *_: prediction(policy)
        )
        changed = replace(policy, title="Archived policy")
        from mari_kit import PollPage, SyncMode
        from mari_kit.sync import plan_sync

        step = plan_sync(
            writer.state(SCOPE, "handbook"),
            PollPage(upserts=(changed,), snapshot_complete=True),
            source_id="handbook",
            mode=SyncMode.INCREMENTAL,
        )

        def fail(stage):
            if stage == "before_commit":
                raise RuntimeError("rollback")

        with pytest.raises(RuntimeError, match="rollback"):
            writer.apply_plan(SCOPE, step, failpoint=fail)
        assert brain.answer("Refund window?", user_id="alice")["cache_hit"]
        writer.apply_plan(SCOPE, step)
        seen = []

        def generate(question, documents):
            seen.extend(documents)
            return prediction(documents[0])

        assert not brain.answer("Refund window?", user_id="alice", generate=generate)[
            "cache_hit"
        ]
        assert seen == [changed]
