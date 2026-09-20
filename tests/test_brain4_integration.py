"""Independent regression tests for corrupted cache records."""

import pytest

from examples.company_brains.durable.cache_records import seal_cache_record
from examples.company_brains.durable.engine import CompanyBrain
from examples.company_brains.durable.store import SQLiteBrainStore
from tests.test_brain2_integration import SCOPE, apply, doc, prediction


def test_single_start_selection_does_not_rescan_levels_quadratically():
    from mari_kit.retrieval import HNSWIndex

    class CountingLevels(dict):
        reads = 0

        def __getitem__(self, key):
            self.reads += 1
            return super().__getitem__(key)

    index = HNSWIndex({str(i): [float(i + 1), 1.0] for i in range(100)}, m=2)
    levels = CountingLevels(index.levels)
    index.levels = levels
    index.search([1.0, 1.0], limit=3)
    assert levels.reads < 1000


@pytest.mark.parametrize("raw", ["{broken", "[]", "null", '"scalar"'])
def test_invalid_json_cache_record_is_a_regenerable_miss(tmp_path, raw):
    with SQLiteBrainStore(tmp_path / "brain.sqlite") as store:
        policy = doc()
        apply(store, policy)
        brain = CompanyBrain(store, SCOPE)
        question = "Refund window?"
        brain.answer(question, user_id="alice", generate=lambda *_: prediction(policy))
        store._connection.execute("UPDATE cache SET payload = ?", (raw,))
        result = brain.answer(
            question, user_id="alice", generate=lambda *_: prediction(policy)
        )
        assert not result["cache_hit"]
        assert result["answer"] == policy.body
        assert brain.answer(question, user_id="alice")["cache_hit"]


def test_evidence_backed_abstention_remains_cacheable(tmp_path):
    with SQLiteBrainStore(tmp_path / "brain.sqlite") as store:
        policy = doc()
        apply(store, policy)
        brain = CompanyBrain(store, SCOPE)
        value = prediction(policy)
        value.update(
            answer="The supplied policy does not resolve this case.",
            disposition="insufficient_evidence",
        )
        brain.answer("Refund exception?", user_id="alice", generate=lambda *_: value)
        result = brain.answer("Refund exception?", user_id="alice")
        assert result["cache_hit"]
        assert result["disposition"] == "insufficient_evidence"


def test_cached_evidence_revision_must_match_live_source(tmp_path):
    with SQLiteBrainStore(tmp_path / "brain.sqlite") as store:
        policy = doc()
        apply(store, policy)
        brain = CompanyBrain(store, SCOPE)
        question = "Refund window?"
        brain.answer(question, user_id="alice", generate=lambda *_: prediction(policy))
        key = brain._cache_key(question, "alice")
        payload = store.load_cache(SCOPE, key)
        payload["evidence"][0]["revision"] = "obsolete"
        store.save_cache(SCOPE, key, seal_cache_record(payload))
        assert not brain.answer(
            question, user_id="alice", generate=lambda *_: prediction(policy)
        )["cache_hit"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("question", "Different?"),
        ("user_id", "bob"),
        ("scope_key", ["other", ""]),
        ("dependencies", [42]),
    ],
)
def test_valid_checksum_does_not_bypass_request_and_shape_checks(
    tmp_path, field, value
):
    with SQLiteBrainStore(tmp_path / "brain.sqlite") as store:
        policy = doc()
        apply(store, policy)
        brain = CompanyBrain(store, SCOPE)
        question = "Refund window?"
        brain.answer(question, user_id="alice", generate=lambda *_: prediction(policy))
        key = brain._cache_key(question, "alice")
        payload = store.load_cache(SCOPE, key)
        payload[field] = value
        store.save_cache(SCOPE, key, seal_cache_record(payload))
        assert not brain.answer(question, user_id="alice")["cache_hit"]


def test_scope_change_retries_even_when_both_tenants_have_identical_sources(tmp_path):
    from mari_kit import PollPage, ScopeRef, SyncMode
    from mari_kit.sync import plan_sync

    other = ScopeRef(tenant="other")
    with SQLiteBrainStore(tmp_path / "brain.sqlite") as store:
        policy = doc()
        apply(store, policy)
        step = plan_sync(
            store.state(other, "handbook"),
            PollPage(upserts=(policy,), snapshot_complete=True),
            source_id="handbook",
            mode=SyncMode.INCREMENTAL,
        )
        store.apply_plan(other, step)
        brain = CompanyBrain(store, SCOPE)
        calls = []

        def generate(question, documents):
            scope = brain.scope
            calls.append(scope)
            brain.scope = other
            value = prediction(documents[0])
            value["answer"] = f"{scope.tenant}: {documents[0].body}"
            return value

        result = brain.answer("Refund window?", user_id="alice", generate=generate)
        assert calls == [SCOPE, other]
        assert result["answer"].startswith("other:")
