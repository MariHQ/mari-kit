"""Wave-5 cache tests: compact authorized digests and precomputed view maps.

Wave 3/4 memoized an authorized view under a cheap access token and bounded the
view cache by count and retained bytes.  Two costs remained:

* the persisted answer record carried the full, per-document authorized
  fingerprint list, so a stored record grew linearly with the number of
  *unrelated* authorized documents even though the answer cited only one; and
* every cache hit rebuilt an O(N) ``document_id -> document`` map to revalidate
  the cited evidence and dependencies.

These tests pin the wave-5 contract:

* the answer schema is bumped to ``company-brain-answer-v3`` and the persisted
  ``authorized_fingerprint`` is one compact 64-character SHA-256 digest of the
  exact authorized set, so a record's stored size does not grow with the size of
  the unrelated authorized corpus;
* legacy v1/v2 records are safe misses that are regenerated as v3;
* the digest and the by-id map are computed once per authorized view, so
  repeated cache hits rebuild neither;
* the public ``authorized_fingerprint`` helper still returns the ordered
  per-document fingerprint tuple;
* every request still checks the live token and validates schema, checksum,
  scope, question, user, dependencies, and exact quotes, including
  cross-connection revocation and same-revision title/ACL/metadata edits.
"""

from __future__ import annotations

from dataclasses import replace

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

SOURCE = "handbook:wave5"
SCOPE = ScopeRef(tenant="wave5", space="brain")
SUPPORT = Principal(kind="team", identifier="support")
FINANCE = Principal(kind="team", identifier="finance")
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
    metadata: dict[str, object] | None = None,
) -> KnowledgeDocument:
    return KnowledgeDocument(
        source_id=SOURCE,
        external_id=external_id,
        title=title,
        body=body,
        revision=revision,
        acl=DocumentACL(visibility=visibility, principals=principals),
        metadata=metadata or {},
    )


TARGET = document("refunds", QUOTE, "v1", title="Refund policy")


def unrelated(index: int) -> KnowledgeDocument:
    return document(
        f"memo-{index}",
        f"Unrelated memo {index} discusses topic {index}.",
        "v1",
        title=f"Memo {index}",
    )


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


def sync_incremental(
    store: SQLiteBrainStore, scope: ScopeRef, document: KnowledgeDocument
) -> None:
    plan = plan_sync(
        store.state(scope, SOURCE),
        PollPage(upserts=(document,), snapshot_complete=True),
        source_id=SOURCE,
        mode=SyncMode.INCREMENTAL,
    )
    store.apply_plan(scope, plan)


def citing_generate(target: KnowledgeDocument):
    """A host callback that always cites ``target`` with its exact body."""

    def generate(question: str, documents: tuple[KnowledgeDocument, ...]):
        return {
            "answer": target.body,
            "disposition": "grounded",
            "evidence": [{"document_id": target.document_id, "quote": target.body}],
        }

    return generate


class CountingStore(SQLiteBrainStore):
    """A store that records how often the engine read the live access state."""

    def __init__(self, path: str) -> None:
        super().__init__(path)
        self.token_reads = 0
        self.snapshot_reads = 0

    def access_token(self, scope: ScopeRef, user_id: str):  # type: ignore[no-untyped-def]
        self.token_reads += 1
        return super().access_token(scope, user_id)

    def access_token_snapshot(self, scope: ScopeRef, user_id: str):  # type: ignore[no-untyped-def]
        self.snapshot_reads += 1
        return super().access_token_snapshot(scope, user_id)


def stored_record(
    store: SQLiteBrainStore, scope: ScopeRef, key: str
) -> dict[str, object]:
    record = store.load_cache(scope, key)
    assert record is not None, "expected a persisted cache record"
    return record


def record_size(record: dict[str, object]) -> int:
    return len(canonical_json_bytes(record))


# --------------------------------------------------------------------------- #
# Compact digest
# --------------------------------------------------------------------------- #


def test_schema_is_v3_and_digest_is_a_compact_sha256(tmp_path: object) -> None:
    with SQLiteBrainStore(str(tmp_path)) as store:
        sync_full(store, SCOPE, TARGET)
        store.set_groups(SCOPE, "alice", {"support"})
        brain = CompanyBrain(store, SCOPE)

        assert brain.answer(QUESTION, user_id="alice")["cache_hit"] is False
        record = stored_record(store, SCOPE, brain._cache_key(QUESTION, "alice"))

        assert engine_module.CACHE_SCHEMA == "company-brain-answer-v3"
        assert record["schema"] == "company-brain-answer-v3"
        digest = record["authorized_fingerprint"]
        assert isinstance(digest, str)
        assert len(digest) == 64
        assert all(character in "0123456789abcdef" for character in digest)
        assert digest == engine_module.authorized_digest((TARGET,))


def test_stored_record_size_is_independent_of_unrelated_authorized_corpus(
    tmp_path: object,
) -> None:
    small_path = str(tmp_path) + "-small"
    large_path = str(tmp_path) + "-large"
    corpus = tuple(unrelated(index) for index in range(150))

    with SQLiteBrainStore(small_path) as store:
        sync_full(store, SCOPE, TARGET)
        store.set_groups(SCOPE, "alice", {"support"})
        brain = CompanyBrain(store, SCOPE)
        brain.answer(QUESTION, user_id="alice", generate=citing_generate(TARGET))
        small = stored_record(store, SCOPE, brain._cache_key(QUESTION, "alice"))

    with SQLiteBrainStore(large_path) as store:
        sync_full(store, SCOPE, TARGET, *corpus)
        store.set_groups(SCOPE, "alice", {"support"})
        brain = CompanyBrain(store, SCOPE)
        result = brain.answer(
            QUESTION, user_id="alice", generate=citing_generate(TARGET)
        )
        assert result["disposition"] == "grounded"
        large = stored_record(store, SCOPE, brain._cache_key(QUESTION, "alice"))

    assert len(small["authorized_fingerprint"]) == 64
    assert len(large["authorized_fingerprint"]) == 64
    # The only authorized-set material persisted is the fixed-width digest, so a
    # 150x larger authorized corpus must not change the stored record size.
    assert record_size(large) == record_size(small)


def test_authorized_fingerprint_helper_still_returns_ordered_tuple() -> None:
    fingerprint = engine_module.authorized_fingerprint((TARGET,))
    assert isinstance(fingerprint, tuple)
    assert len(fingerprint) == 1
    assert isinstance(fingerprint[0], str) and len(fingerprint[0]) == 64
    assert engine_module.authorized_digest(
        (TARGET,)
    ) == engine_module.fingerprint_digest(fingerprint)


# --------------------------------------------------------------------------- #
# Precomputed view map and digest
# --------------------------------------------------------------------------- #


def test_repeated_cache_hits_do_not_rebuild_maps_or_fingerprint(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"fingerprint": 0, "digest": 0}
    real_fingerprint = engine_module.authorized_fingerprint
    real_digest = engine_module.fingerprint_digest

    def counting_fingerprint(documents):  # type: ignore[no-untyped-def]
        calls["fingerprint"] += 1
        return real_fingerprint(documents)

    def counting_digest(fingerprint):  # type: ignore[no-untyped-def]
        calls["digest"] += 1
        return real_digest(fingerprint)

    monkeypatch.setattr(engine_module, "authorized_fingerprint", counting_fingerprint)
    monkeypatch.setattr(engine_module, "fingerprint_digest", counting_digest)

    with SQLiteBrainStore(str(tmp_path)) as store:
        sync_full(store, SCOPE, TARGET, unrelated(1), unrelated(2))
        store.set_groups(SCOPE, "alice", {"support"})
        brain = CompanyBrain(store, SCOPE)

        assert brain.answer(QUESTION, user_id="alice")["cache_hit"] is False
        assert calls == {"fingerprint": 1, "digest": 1}

        view = brain._view("alice")
        map_identity = id(view._by_id)
        digest = view.digest

        for _ in range(5):
            hit = brain.answer(QUESTION, user_id="alice")
            assert hit["cache_hit"] is True

        assert calls == {"fingerprint": 1, "digest": 1}
        assert brain._view("alice") is view
        assert id(view._by_id) == map_identity
        assert view.digest == digest


def test_view_precomputes_a_by_id_map_over_the_same_documents(
    tmp_path: object,
) -> None:
    with SQLiteBrainStore(str(tmp_path)) as store:
        sync_full(store, SCOPE, TARGET, unrelated(1))
        store.set_groups(SCOPE, "alice", {"support"})
        brain = CompanyBrain(store, SCOPE)
        brain.search(QUERY, user_id="alice")

        view = brain._view("alice")
        assert set(view._by_id) == {doc.document_id for doc in view.documents}
        for document in view.documents:
            assert view._by_id[document.document_id] is document


# --------------------------------------------------------------------------- #
# Legacy records and live validation
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "legacy_schema", ["company-brain-answer-v1", "company-brain-answer-v2"]
)
@pytest.mark.parametrize("fingerprint", ["list", "string"])
def test_legacy_records_are_safe_misses_and_regenerate_as_v3(
    tmp_path: object, legacy_schema: str, fingerprint: str
) -> None:
    with SQLiteBrainStore(str(tmp_path)) as store:
        sync_full(store, SCOPE, TARGET)
        store.set_groups(SCOPE, "alice", {"support"})
        brain = CompanyBrain(store, SCOPE)
        key = brain._cache_key(QUESTION, "alice")
        assert brain.answer(QUESTION, user_id="alice")["cache_hit"] is False

        legacy = dict(stored_record(store, SCOPE, key))
        legacy["schema"] = legacy_schema
        digest = legacy["authorized_fingerprint"]
        legacy["authorized_fingerprint"] = [digest] if fingerprint == "list" else digest
        store.save_cache(SCOPE, key, seal_cache_record(legacy))

        regenerated = brain.answer(QUESTION, user_id="alice")
        assert regenerated["cache_hit"] is False
        assert regenerated["disposition"] == "grounded"
        assert QUOTE in regenerated["answer"]

        upgraded = stored_record(store, SCOPE, key)
        assert upgraded["schema"] == "company-brain-answer-v3"
        assert isinstance(upgraded["authorized_fingerprint"], str)
        assert brain.answer(QUESTION, user_id="alice")["cache_hit"] is True


@pytest.mark.parametrize("poison", ["missing", "empty", "list"])
def test_missing_or_non_string_digest_is_never_served(
    tmp_path: object, poison: str
) -> None:
    with SQLiteBrainStore(str(tmp_path)) as store:
        sync_full(store, SCOPE, TARGET)
        store.set_groups(SCOPE, "alice", {"support"})
        brain = CompanyBrain(store, SCOPE)
        key = brain._cache_key(QUESTION, "alice")
        brain.answer(QUESTION, user_id="alice")

        poisoned = dict(stored_record(store, SCOPE, key))
        if poison == "missing":
            poisoned.pop("authorized_fingerprint", None)
        elif poison == "empty":
            poisoned["authorized_fingerprint"] = ""
        else:
            poisoned["authorized_fingerprint"] = [poisoned["authorized_fingerprint"]]
        store.save_cache(SCOPE, key, seal_cache_record(poisoned))

        result = brain.answer(QUESTION, user_id="alice")
        assert result["cache_hit"] is False
        assert QUOTE in result["answer"]


def test_cross_connection_revocation_and_edit_invalidate_cached_answer(
    tmp_path: object,
) -> None:
    writer = SQLiteBrainStore(str(tmp_path))
    reader = CountingStore(str(tmp_path))
    try:
        sync_full(writer, SCOPE, TARGET)
        writer.set_groups(SCOPE, "alice", {"support"})
        brain = CompanyBrain(reader, SCOPE)

        warm = brain.answer(QUESTION, user_id="alice")
        assert warm["cache_hit"] is False
        assert warm["disposition"] == "grounded"
        assert reader.snapshot_reads == 1

        hit = brain.answer(QUESTION, user_id="alice")
        assert hit["cache_hit"] is True
        assert reader.snapshot_reads == 1

        # A membership change committed on another connection must revoke the
        # cached answer; the live token is re-read on every request.
        writer.set_groups(SCOPE, "alice", set())
        revoked = brain.answer(QUESTION, user_id="alice")
        assert revoked["cache_hit"] is False
        assert revoked["disposition"] == "insufficient_evidence"
        assert QUOTE not in revoked["answer"]
        assert reader.snapshot_reads == 2

        writer.set_groups(SCOPE, "alice", {"support"})
        edited = replace(
            TARGET, body="The refund window is 45 days.", content_digest=""
        )
        sync_full(writer, SCOPE, edited)
        refreshed = brain.answer(QUESTION, user_id="alice")
        assert refreshed["cache_hit"] is False
        assert "45 days" in refreshed["answer"]
    finally:
        reader.close()
        writer.close()


@pytest.mark.parametrize(
    "mutation",
    [
        {"title": "Archived refund policy"},
        {"metadata": {"classification": "internal"}},
        {"acl": DocumentACL(visibility="restricted", principals=(SUPPORT, FINANCE))},
    ],
)
def test_same_revision_title_metadata_acl_edits_invalidate_digest(
    tmp_path: object, mutation: dict[str, object]
) -> None:
    """The digest covers title, metadata, and ACL, not only body and revision."""

    with SQLiteBrainStore(str(tmp_path)) as store:
        sync_full(store, SCOPE, TARGET)
        store.set_groups(SCOPE, "alice", {"support"})
        # Force a fresh view per request so only the persisted digest can
        # invalidate the cached record, not the memoized view token.
        store.access_token = None  # type: ignore[method-assign]
        store.access_token_snapshot = None  # type: ignore[method-assign]
        brain = CompanyBrain(store, SCOPE)

        before = brain.answer(QUESTION, user_id="alice")
        assert before["cache_hit"] is False
        assert brain.answer(QUESTION, user_id="alice")["cache_hit"] is True

        changed = replace(TARGET, content_digest="", **mutation)
        assert changed.revision == TARGET.revision
        assert engine_module.authorized_digest((changed,)) != (
            engine_module.authorized_digest((TARGET,))
        )
        sync_incremental(store, SCOPE, changed)

        after = brain.answer(QUESTION, user_id="alice")
        assert after["cache_hit"] is False
        assert engine_module.authorized_digest((changed,)) != (
            engine_module.authorized_digest((TARGET,))
        )


def test_cache_hit_revalidates_dependencies_and_exact_quotes(
    tmp_path: object,
) -> None:
    with SQLiteBrainStore(str(tmp_path)) as store:
        sync_full(store, SCOPE, TARGET)
        store.set_groups(SCOPE, "alice", {"support"})
        brain = CompanyBrain(store, SCOPE)
        key = brain._cache_key(QUESTION, "alice")
        brain.answer(QUESTION, user_id="alice")
        base = dict(stored_record(store, SCOPE, key))

        tampered = dict(base)
        dependencies = [dict(row) for row in base["dependencies"]]
        dependencies[0]["content_digest"] = "deadbeef"
        tampered["dependencies"] = dependencies
        store.save_cache(SCOPE, key, seal_cache_record(tampered))
        assert brain.answer(QUESTION, user_id="alice")["cache_hit"] is False

        forged = dict(base)
        evidence = [dict(row) for row in base["evidence"]]
        evidence[0]["quote"] = "A quote that is not in the document."
        forged["evidence"] = evidence
        store.save_cache(SCOPE, key, seal_cache_record(forged))
        assert brain.answer(QUESTION, user_id="alice")["cache_hit"] is False

        offset = dict(base)
        evidence = [dict(row) for row in base["evidence"]]
        evidence[0].update({"start": 0, "end": 1})
        offset["evidence"] = evidence
        store.save_cache(SCOPE, key, seal_cache_record(offset))
        assert brain.answer(QUESTION, user_id="alice")["cache_hit"] is False


def test_generate_rechecks_a_title_change_during_the_callback(
    tmp_path: object,
) -> None:
    writer = SQLiteBrainStore(str(tmp_path))
    reader = SQLiteBrainStore(str(tmp_path))
    try:
        sync_full(writer, SCOPE, TARGET)
        writer.set_groups(SCOPE, "alice", {"support"})
        brain = CompanyBrain(reader, SCOPE)
        titles: list[tuple[str, ...]] = []

        def generate(question: str, documents: tuple[KnowledgeDocument, ...]):
            titles.append(tuple(row.title for row in documents))
            if len(titles) == 1:
                sync_incremental(
                    writer,
                    SCOPE,
                    replace(TARGET, title="Renamed policy", content_digest=""),
                )
            return {
                "answer": QUOTE,
                "disposition": "grounded",
                "evidence": [{"document_id": TARGET.document_id, "quote": QUOTE}],
            }

        result = brain.answer(QUESTION, user_id="alice", generate=generate)

        assert titles[0] == ("Refund policy",)
        assert titles[-1] == ("Renamed policy",)
        assert result["cache_hit"] is False
        assert result["disposition"] == "grounded"
        assert QUOTE in result["answer"]
    finally:
        reader.close()
        writer.close()
