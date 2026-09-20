"""Wave-6 validation tests for the durable company-brain cache boundary.

These tests attack the host-owned persisted answer record from the point of view
of a *trusted but corrupt writer*: the SQLite file is host-owned, so a writer can
corrupt a stored record or deliberately recompute the unkeyed checksum after
tampering.  They never edit the engine or the validator.

The wave-6 contract is negative and defensive:

* every malformed but JSON-compatible field combination, when re-sealed and
  persisted, recovers as an ordinary cache miss and never raises out of
  ``CompanyBrain.answer``;
* a genuine evidence-backed abstention record (``insufficient_evidence`` with
  matching evidence and dependencies) is a valid reusable record;
* the checksum detects accidental corruption, and request identity, scope,
  schema, digest, dependencies, revisions, quotes, and evidence spans are all
  rechecked on every hit;
* the checksum is *not* authentication.  A writer that can re-seal a record can
  also inject unsupported prose; that residual is asserted explicitly so no test
  presents the checksum as protection against a malicious re-sealer.

Two concrete ``SQLiteBrainStore.load_cache`` bugs were reproduced at the wave-6
baseline and are guarded here:

1. a non-UTF-8 ``BLOB`` payload raised ``UnicodeDecodeError`` out of
   ``load_cache``/``answer`` instead of reading as a miss; and
2. a payload containing an integer literal longer than Python's default
   4300-digit int<->str conversion limit raised a bare ``ValueError`` out of
   ``json.loads``.

``store.py`` now treats any decode failure (invalid text, non-UTF-8 bytes,
over-long integer literal, or pathologically nested JSON) as a cache miss.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest

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
from mari_kit.sync import plan_sync

SOURCE = "wave6:handbook"
SCOPE = ScopeRef(tenant="wave6", space="brain")
SUPPORT = Principal(kind="team", identifier="support")
USER = "alice"
QUESTION = "What is the refund window?"
QUOTE = "The refund window is 30 days."
DOCUMENT = KnowledgeDocument(
    source_id=SOURCE,
    external_id="refunds",
    title="Refund policy",
    body=QUOTE,
    revision="v1",
    acl=DocumentACL(visibility="restricted", principals=(SUPPORT,)),
)


# --------------------------------------------------------------------------- #
# Fixtures and helpers
# --------------------------------------------------------------------------- #


def _sync_full(store: SQLiteBrainStore) -> None:
    plan = plan_sync(
        store.state(SCOPE, SOURCE),
        PollPage(upserts=(DOCUMENT,), snapshot_complete=True),
        source_id=SOURCE,
        mode=SyncMode.FULL,
    )
    store.apply_plan(SCOPE, plan)


@pytest.fixture
def cached_brain(
    tmp_path: Path,
) -> Iterator[tuple[SQLiteBrainStore, CompanyBrain, str, dict]]:
    """A warm grounded record plus the store, brain, and cache key."""

    store = SQLiteBrainStore(tmp_path / "cache.sqlite3")
    _sync_full(store)
    store.set_groups(SCOPE, USER, {"support"})
    brain = CompanyBrain(store, SCOPE)
    key = brain._cache_key(QUESTION, USER)
    warm = brain.answer(QUESTION, user_id=USER)
    assert warm["disposition"] == "grounded"
    assert warm["cache_hit"] is False
    base = store.load_cache(SCOPE, key)
    assert isinstance(base, dict)
    try:
        yield store, brain, key, base
    finally:
        store.close()


def _mutated(record: Mapping[str, object], **changes: object) -> dict:
    """Deep-copy a persisted record and overwrite top-level fields."""

    result = json.loads(json.dumps(record))
    result.update(changes)
    return result


def _evidence(base: Mapping[str, object]) -> dict:
    return json.loads(json.dumps(base["evidence"][0]))  # type: ignore[index]


def _with_evidence(base: Mapping[str, object], row: Mapping[str, object]) -> dict:
    result = json.loads(json.dumps(base))
    result["evidence"] = [dict(row)]
    return result


def _offsets(base: Mapping[str, object], **changes: object) -> dict:
    row = _evidence(base)
    row.update(changes)
    return _with_evidence(base, row)


def _drop_offsets(base: Mapping[str, object], *keys: str) -> dict:
    row = _evidence(base)
    for key in keys:
        row.pop(key, None)
    return _with_evidence(base, row)


def _install(store: SQLiteBrainStore, key: str, record: Mapping[str, object]) -> None:
    store.save_cache(SCOPE, key, seal_cache_record(record))


def _raw_put(store: SQLiteBrainStore, key: str, value: object) -> None:
    """Write a raw ``cache.payload`` value, bypassing the app encoder."""

    store._connection.execute(  # noqa: SLF001 - host inspection of its own DB
        "INSERT OR REPLACE INTO cache (tenant, space, cache_key, payload) "
        "VALUES (?, ?, ?, ?)",
        (*SCOPE.key, key, value),
    )


def _assert_safe(result: Mapping[str, object]) -> None:
    assert set(result) == {"answer", "disposition", "evidence", "cache_hit"}
    assert isinstance(result["answer"], str) and result["answer"]
    assert result["disposition"] in {"grounded", "insufficient_evidence"}
    assert isinstance(result["evidence"], list)
    assert isinstance(result["cache_hit"], bool)


def _assert_recovered(result: Mapping[str, object]) -> None:
    """A rejected record must fall through to a fresh grounded abstention-free answer."""

    _assert_safe(result)
    assert result["cache_hit"] is False
    assert result["disposition"] == "grounded"
    assert QUOTE in str(result["answer"])


# --------------------------------------------------------------------------- #
# Store cache decoding
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "payload",
    ["null", "[]", "42", "true", "false", '"text"', "3.14", "nan", "{}"],
)
def test_load_cache_decodes_non_object_json_safely(
    cached_brain: tuple[SQLiteBrainStore, CompanyBrain, str, dict], payload: str
) -> None:
    store, brain, key, _ = cached_brain
    _raw_put(store, key, payload)
    loaded = store.load_cache(SCOPE, key)
    assert loaded is None or loaded == {}
    _assert_recovered(brain.answer(QUESTION, user_id=USER))


@pytest.mark.parametrize(
    "payload",
    ["", "not json", "{", '{"a":}', "[]]", "\ufeff{}", '{"a": 1,}'],
)
def test_load_cache_rejects_undecodable_text(
    cached_brain: tuple[SQLiteBrainStore, CompanyBrain, str, dict], payload: str
) -> None:
    store, brain, key, _ = cached_brain
    _raw_put(store, key, payload)
    assert store.load_cache(SCOPE, key) is None
    _assert_recovered(brain.answer(QUESTION, user_id=USER))


@pytest.mark.parametrize(
    "payload",
    [b"\xff\xff\xff", b"\xff\xfe\x00", b"\x80", b"\xc3\x28", b"\xed\xa0\x80"],
)
def test_load_cache_survives_non_utf8_blob_payload(
    cached_brain: tuple[SQLiteBrainStore, CompanyBrain, str, dict], payload: bytes
) -> None:
    """Regression: a non-UTF-8 BLOB must be a miss, not a UnicodeDecodeError."""

    store, brain, key, _ = cached_brain
    _raw_put(store, key, payload)
    assert store.load_cache(SCOPE, key) is None
    _assert_recovered(brain.answer(QUESTION, user_id=USER))


def test_load_cache_still_decodes_valid_blob_payload(
    cached_brain: tuple[SQLiteBrainStore, CompanyBrain, str, dict],
) -> None:
    """Positive control: valid UTF-8/UTF-16 JSON bytes still decode to a dict."""

    store, _, key, _ = cached_brain
    for encoding in ("utf-8", "utf-16"):
        raw = json.dumps({"answer": "x"}).encode(encoding)
        _raw_put(store, key, raw)
        assert store.load_cache(SCOPE, key) == {"answer": "x"}


def test_load_cache_survives_over_long_integer_literal(
    cached_brain: tuple[SQLiteBrainStore, CompanyBrain, str, dict],
) -> None:
    """Regression: an over-long integer offset must be a miss, not a ValueError."""

    store, brain, key, base = cached_brain
    start = base["evidence"][0]["start"]
    raw = json.dumps(base)
    needle = f'"start": {start}'
    assert needle in raw
    raw = raw.replace(needle, f'"start": {"9" * 100_000}', 1)
    _raw_put(store, key, raw)
    assert store.load_cache(SCOPE, key) is None
    _assert_recovered(brain.answer(QUESTION, user_id=USER))


def test_load_cache_survives_deeply_nested_payload(
    cached_brain: tuple[SQLiteBrainStore, CompanyBrain, str, dict],
) -> None:
    store, brain, key, _ = cached_brain
    depth = 100_000
    _raw_put(store, key, "[" * depth + "]" * depth)
    assert store.load_cache(SCOPE, key) is None
    _assert_recovered(brain.answer(QUESTION, user_id=USER))


def test_load_cache_tolerates_non_finite_number(
    cached_brain: tuple[SQLiteBrainStore, CompanyBrain, str, dict],
) -> None:
    """A payload Python's JSON parser accepts but the codec rejects is a miss."""

    store, brain, key, _ = cached_brain
    _raw_put(store, key, '{"checksum": NaN, "answer": "x"}')
    assert isinstance(store.load_cache(SCOPE, key), dict)
    _assert_recovered(brain.answer(QUESTION, user_id=USER))


def test_engine_recovers_and_recaches_after_corrupt_payload(
    cached_brain: tuple[SQLiteBrainStore, CompanyBrain, str, dict],
) -> None:
    """After any corrupt row, the next request regenerates and the one after hits."""

    store, brain, key, _ = cached_brain
    corrupt: tuple[object, ...] = (
        b"\xff\xff",
        "not json",
        "null",
        '{"start": ' + "9" * 100_000 + "}",
    )
    for value in corrupt:
        _raw_put(store, key, value)
        first = brain.answer(QUESTION, user_id=USER)
        _assert_recovered(first)
        second = brain.answer(QUESTION, user_id=USER)
        assert second["cache_hit"] is True
        assert QUOTE in str(second["answer"])


# --------------------------------------------------------------------------- #
# Structurally invalid field combinations (property-like, re-sealed)
# --------------------------------------------------------------------------- #

_INVALID_VALUES: dict[str, tuple[object, ...]] = {
    "schema": (None, "", "company-brain-answer-v2", 5, [], {}),
    "question": (None, "", "A different question?", 5, [], {}),
    "user_id": (None, "", "mallory", 5, [], {}),
    "scope_key": (
        None,
        "",
        [],
        ["wave6"],
        ["wave6", "brain", "extra"],
        [1, "brain"],
        {},
    ),
    "answer": (None, "", "   ", 5, [], {}),
    "disposition": (None, "", "totally-bogus", 5, [], {}),
    "authorized_fingerprint": (None, "", "   ", 5, [], {}, ["a" * 64]),
    "evidence": (
        None,
        "x",
        5,
        {},
        [None],
        [5],
        ["x"],
        [{}],
        [{"document_id": "refunds"}],
    ),
    "dependencies": (
        None,
        "x",
        5,
        {},
        [None],
        [5],
        ["x"],
        [{}],
        [{"document_id": "refunds"}],
    ),
}


@pytest.mark.parametrize("field", sorted(_INVALID_VALUES))
def test_structurally_invalid_resealed_field_is_a_miss(
    cached_brain: tuple[SQLiteBrainStore, CompanyBrain, str, dict], field: str
) -> None:
    store, brain, key, base = cached_brain
    for poison in _INVALID_VALUES[field]:
        _install(store, key, _mutated(base, **{field: poison}))
        result = brain.answer(QUESTION, user_id=USER)
        _assert_recovered(result)
        assert result["cache_hit"] is False, (field, poison)


# --------------------------------------------------------------------------- #
# Digest, checksum, and request binding
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "changes",
    [
        {"question": "A different question?"},
        {"user_id": "mallory"},
        {"scope_key": ["other-tenant", "brain"]},
        {"schema": "company-brain-answer-v2"},
    ],
)
def test_resealed_cross_request_binding_is_a_miss(
    cached_brain: tuple[SQLiteBrainStore, CompanyBrain, str, dict],
    changes: dict[str, object],
) -> None:
    store, brain, key, base = cached_brain
    _install(store, key, _mutated(base, **changes))
    _assert_recovered(brain.answer(QUESTION, user_id=USER))


def test_resealed_wrong_digest_is_a_miss(
    cached_brain: tuple[SQLiteBrainStore, CompanyBrain, str, dict],
) -> None:
    store, brain, key, base = cached_brain
    _install(store, key, _mutated(base, authorized_fingerprint="0" * 64))
    _assert_recovered(brain.answer(QUESTION, user_id=USER))


@pytest.mark.parametrize(
    "changes",
    [
        {"answer": "ACCIDENTALLY-CORRUPTED"},
        {"authorized_fingerprint": "0" * 64},
        {"disposition": "bogus"},
        {"question": "A different question?"},
    ],
)
def test_accidental_corruption_without_reseal_is_a_miss(
    cached_brain: tuple[SQLiteBrainStore, CompanyBrain, str, dict],
    changes: dict[str, object],
) -> None:
    store, brain, key, base = cached_brain
    store.save_cache(SCOPE, key, _mutated(base, **changes))
    _assert_recovered(brain.answer(QUESTION, user_id=USER))


def test_resealed_unchanged_record_is_still_reused(
    cached_brain: tuple[SQLiteBrainStore, CompanyBrain, str, dict],
) -> None:
    """Positive control: the validator is not simply rejecting every record."""

    store, brain, key, base = cached_brain
    _install(store, key, _mutated(base))
    result = brain.answer(QUESTION, user_id=USER)
    _assert_safe(result)
    assert result["cache_hit"] is True
    assert result["answer"] == base["answer"]


@pytest.mark.parametrize(
    "changes",
    [
        {
            "dependencies": [
                {
                    "document_id": "refunds",
                    "revision": "v1",
                    "content_digest": "deadbeef",
                }
            ]
        },
        {
            "evidence": [
                {"document_id": "refunds", "revision": "v1", "quote": "not in body"}
            ]
        },
    ],
)
def test_resealed_dependency_or_quote_mismatch_is_a_miss(
    cached_brain: tuple[SQLiteBrainStore, CompanyBrain, str, dict],
    changes: dict[str, object],
) -> None:
    store, brain, key, base = cached_brain
    _install(store, key, _mutated(base, **changes))
    _assert_recovered(brain.answer(QUESTION, user_id=USER))


# --------------------------------------------------------------------------- #
# Extreme and invalid evidence offsets
# --------------------------------------------------------------------------- #


def test_invalid_evidence_offsets_are_a_miss(
    cached_brain: tuple[SQLiteBrainStore, CompanyBrain, str, dict],
) -> None:
    store, brain, key, base = cached_brain
    length = len(QUOTE)
    invalid: tuple[dict, ...] = (
        _drop_offsets(base, "end"),
        _drop_offsets(base, "start"),
        _offsets(base, start=None),
        _offsets(base, end=None),
        _offsets(base, start=-1, end=length),
        _offsets(base, start=-(10**100), end=length),
        _offsets(base, start=length, end=length),
        _offsets(base, start=length, end=length - 1),
        _offsets(base, start=0.0, end=float(length)),
        _offsets(base, start=True, end=length),
        _offsets(base, start=0, end=False),
        _offsets(base, start="0", end=str(length)),
        _offsets(base, start=0, end=str(length)),
    )
    for poisoned in invalid:
        _install(store, key, poisoned)
        _assert_recovered(brain.answer(QUESTION, user_id=USER))


def test_extreme_but_well_formed_offsets_never_raise(
    cached_brain: tuple[SQLiteBrainStore, CompanyBrain, str, dict],
) -> None:
    store, brain, key, base = cached_brain
    accepted = (
        _offsets(base, start=0, end=10**6),
        _offsets(base, start=0, end=10**4000),
        _drop_offsets(base, "start", "end"),
    )
    for poisoned in accepted:
        _install(store, key, poisoned)
        result = brain.answer(QUESTION, user_id=USER)
        _assert_safe(result)
        assert result["cache_hit"] is True
        assert QUOTE in str(result["answer"])

    rejected = _offsets(base, start=10**4000, end=10**4000 + 1)
    _install(store, key, rejected)
    _assert_recovered(brain.answer(QUESTION, user_id=USER))


# --------------------------------------------------------------------------- #
# Valid abstentions and the explicit re-sealing trust boundary
# --------------------------------------------------------------------------- #


def test_valid_evidence_backed_abstention_is_reused(
    cached_brain: tuple[SQLiteBrainStore, CompanyBrain, str, dict],
) -> None:
    """An ``insufficient_evidence`` record that still cites valid evidence is valid."""

    store, brain, key, base = cached_brain
    _install(
        store,
        key,
        _mutated(base, disposition="insufficient_evidence", answer="Not certain."),
    )
    result = brain.answer(QUESTION, user_id=USER)
    _assert_safe(result)
    assert result["cache_hit"] is True
    assert result["disposition"] == "insufficient_evidence"
    assert result["evidence"] == base["evidence"]
    assert result["answer"] == "Not certain."


def test_resealed_unsupported_prose_is_served_documenting_the_limit(
    cached_brain: tuple[SQLiteBrainStore, CompanyBrain, str, dict],
) -> None:
    """The unkeyed checksum is not authentication.

    A writer that can re-seal a record can keep every structurally checked field
    valid (digest, dependencies, revision, exact quote, span) while replacing the
    answer prose with an unsupported claim.  The engine serves it.  This test
    records that limit explicitly so the checksum is never presented as
    protection against a malicious re-sealer.
    """

    store, brain, key, base = cached_brain
    lie = "The refund window is 900 days."
    _install(store, key, _mutated(base, answer=lie))
    result = brain.answer(QUESTION, user_id=USER)
    _assert_safe(result)
    assert result["cache_hit"] is True
    assert result["answer"] == lie
    assert result["disposition"] == "grounded"
