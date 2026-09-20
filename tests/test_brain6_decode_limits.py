"""Recoverable cache misses when stored JSON exceeds interpreter limits."""

import json
import sys

import pytest

from examples.company_brains.durable.store import SQLiteBrainStore
from mari_kit import ScopeRef


def test_deep_extra_field_cannot_crash_checksum_verification(tmp_path):
    from examples.company_brains.durable.engine import CompanyBrain
    from tests.test_brain2_integration import SCOPE, apply, doc, prediction

    with SQLiteBrainStore(tmp_path / "brain.sqlite") as store:
        policy = doc()
        apply(store, policy)
        brain = CompanyBrain(store, SCOPE)
        question = "Refund window?"
        brain.answer(question, user_id="alice", generate=lambda *_: prediction(policy))
        record = store.load_cache(SCOPE, brain._cache_key(question, "alice"))
        depth = sys.getrecursionlimit() + 100
        raw = (
            json.dumps(record)[:-1]
            + ',"extra":'
            + "[" * depth
            + "0"
            + "]" * depth
            + "}"
        )
        store._connection.execute("UPDATE cache SET payload = ?", (raw,))
        result = brain.answer(
            question, user_id="alice", generate=lambda *_: prediction(policy)
        )
        assert not result["cache_hit"]
        assert result["answer"] == policy.body


def test_integer_decode_limit_is_a_miss_not_a_request_failure(tmp_path):
    limit = sys.get_int_max_str_digits()
    if limit == 0:
        pytest.skip("Interpreter integer conversion limit is disabled")
    raw = '{"value":' + "1" * (limit + 1) + "}"
    scope = ScopeRef(tenant="decode-limits")
    with SQLiteBrainStore(tmp_path / "brain.sqlite") as store:
        store.save_cache(scope, "entry", {"valid": True})
        store._connection.execute("UPDATE cache SET payload = ?", (raw,))
        assert store.load_cache(scope, "entry") is None
        store.save_cache(scope, "entry", {"valid": True})
        assert store.load_cache(scope, "entry") == {"valid": True}
