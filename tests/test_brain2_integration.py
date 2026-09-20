from dataclasses import replace

import pytest

from examples.company_brains.durable.engine import CompanyBrain
from examples.company_brains.durable.store import SQLiteBrainStore
from mari_kit import KnowledgeDocument, PollPage, ScopeRef, SyncMode
from mari_kit.sync import plan_sync

SCOPE = ScopeRef(tenant="integration")


def doc(identity="policy", body="Refunds are available for 30 days.", **kwargs):
    return KnowledgeDocument(
        source_id="handbook",
        external_id=identity,
        title="Refund policy",
        body=body,
        revision="v1",
        **kwargs,
    )


def apply(store, document):
    step = plan_sync(
        store.state(SCOPE, "handbook"),
        PollPage(upserts=(document,), snapshot_complete=True),
        source_id="handbook",
        mode=SyncMode.INCREMENTAL,
    )
    store.apply_plan(SCOPE, step)
    return step


def prediction(document):
    return {
        "answer": document.body,
        "disposition": "grounded",
        "evidence": [{"document_id": document.document_id, "quote": document.body}],
    }


def test_contention_abstention_does_not_poison_persisted_answer_cache(tmp_path):
    with SQLiteBrainStore(tmp_path / "brain.sqlite") as store:
        policy = doc()
        apply(store, policy)
        brain = CompanyBrain(store, SCOPE)
        calls = []

        def racing(question, documents):
            calls.append(question)
            apply(store, doc(f"unrelated-{len(calls)}", "An unrelated source arrived."))
            return prediction(policy)

        blocked = brain.answer("Refund window?", user_id="alice", generate=racing)
        assert blocked["disposition"] == "insufficient_evidence"
        assert len(calls) == 3
        recovered = brain.answer(
            "Refund window?", user_id="alice", generate=lambda *_: prediction(policy)
        )
        assert recovered["disposition"] == "grounded"
        assert recovered["cache_hit"] is False
        assert brain.answer("Refund window?", user_id="alice")["cache_hit"] is True


def test_title_only_observation_invalidates_cache_after_restart(tmp_path):
    path = tmp_path / "brain.sqlite"
    initial = doc()
    with SQLiteBrainStore(path) as store:
        apply(store, initial)
        CompanyBrain(store, SCOPE).answer(
            "Refund window?", user_id="alice", generate=lambda *_: prediction(initial)
        )
        apply(store, replace(initial, title="Archived refund policy"))
    with SQLiteBrainStore(path) as store:
        calls = []

        def after_edit(question, documents):
            calls.append(documents[0].title)
            return {
                "answer": "The current policy is not supplied.",
                "disposition": "insufficient_evidence",
                "evidence": [],
            }

        answer = CompanyBrain(store, SCOPE).answer(
            "Refund window?", user_id="alice", generate=after_edit
        )
        assert calls == ["Archived refund policy"]
        assert not answer["cache_hit"]
        assert answer["disposition"] == "insufficient_evidence"


@pytest.mark.parametrize("generation", [0, 2])
def test_store_rejects_malformed_generation_without_writes(tmp_path, generation):
    with SQLiteBrainStore(tmp_path / "brain.sqlite") as store:
        step = plan_sync(
            store.state(SCOPE, "handbook"),
            PollPage(upserts=(doc(),), snapshot_complete=True),
            source_id="handbook",
            mode=SyncMode.FULL,
        )
        malformed = replace(step, state=replace(step.state, generation=generation))
        with pytest.raises(ValueError, match="advance by exactly one"):
            store.apply_plan(SCOPE, malformed)
        assert store.documents(SCOPE) == ()
        assert store.projection(SCOPE) == {}
        assert store.state(SCOPE, "handbook").generation == 0
