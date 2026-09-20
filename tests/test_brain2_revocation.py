"""Adversarial revocation and isolation coverage for the durable company brain.

These tests attack the *shared* store/engine contract from the wave-2 durable
example. They are integration tests: they observe only the documented public
surface of ``SQLiteBrainStore`` and ``CompanyBrain`` and never reach into either
implementation. The properties under attack are:

* two tenants may hold byte-identical provider IDs without crossing;
* a cached answer must not survive a same-revision ACL revocation, a group
  removal, a public-to-restricted change, a deletion, or a source edit;
* a callback may mutate source or membership during generation, and the engine
  must re-authorize before serving the result;
* an output that cites a hidden document must never leak that document's text;
* an authorized user must keep working after somebody else is revoked.

The assertions read the whole JSON response, not just the answer field, so a
citation, an evidence quote, or a cached payload cannot smuggle hidden prose.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from examples.company_brains.durable.engine import CompanyBrain
from examples.company_brains.durable.store import SQLiteBrainStore
from mari_kit import (
    DocumentACL,
    KnowledgeDocument,
    PollPage,
    Principal,
    ScopeRef,
    SyncMode,
    Tombstone,
)
from mari_kit.sync import plan_sync

SOURCE = "confluence:acme"
TENANT_A = ScopeRef(tenant="tenant-a", space="company-brain")
TENANT_B = ScopeRef(tenant="tenant-b", space="company-brain")

FINANCE_SECRET = "The Zephyr refund ceiling for finance is 2000000 credits."
FINANCE_QUESTION = "What is the Zephyr refund ceiling for finance?"
SUPPORT_SECRET = "The Zephyr refund ceiling for support is 7000000 credits."
SUPPORT_QUESTION = "What is the Zephyr refund ceiling for support?"
PUBLIC_BODY = "The Quokka standard refund window is five business days."
PUBLIC_QUESTION = "What is the Quokka standard refund window?"
HIDDEN_SECRET = "The Nimbus secret refund ceiling is 9999999 credits."
HIDDEN_QUESTION = "What is the Nimbus refund ceiling?"
UPDATED_FINANCE_SECRET = "The Zephyr refund ceiling for finance is 3000000 credits."


@pytest.fixture
def store(tmp_path: Path) -> Iterator[SQLiteBrainStore]:
    instance = SQLiteBrainStore(str(tmp_path / "brain.sqlite3"))
    try:
        yield instance
    finally:
        instance.close()


def _acl(*groups: str, visibility: str = "restricted") -> DocumentACL:
    return DocumentACL(
        visibility=visibility,
        principals=tuple(Principal(kind="team", identifier=group) for group in groups),
    )


def _document(
    external_id: str,
    body: str,
    *,
    source: str = SOURCE,
    revision: str = "r1",
    title: str | None = None,
    acl: DocumentACL | None = None,
) -> KnowledgeDocument:
    return KnowledgeDocument(
        source_id=source,
        external_id=external_id,
        title=title or external_id,
        body=body,
        revision=revision,
        acl=acl if acl is not None else DocumentACL(visibility="public"),
    )


def _apply_full(
    store: SQLiteBrainStore, scope: ScopeRef, documents: tuple[KnowledgeDocument, ...]
) -> None:
    state = store.state(scope, SOURCE)
    plan = plan_sync(
        state,
        PollPage(upserts=documents, snapshot_complete=True),
        source_id=SOURCE,
        mode=SyncMode.FULL,
    )
    store.apply_plan(scope, plan)


def _apply_change(
    store: SQLiteBrainStore,
    scope: ScopeRef,
    *,
    upserts: tuple[KnowledgeDocument, ...] = (),
    tombstones: tuple[Tombstone, ...] = (),
) -> None:
    state = store.state(scope, SOURCE)
    plan = plan_sync(
        state,
        PollPage(upserts=upserts, tombstones=tombstones, snapshot_complete=True),
        source_id=SOURCE,
        mode=SyncMode.INCREMENTAL,
    )
    store.apply_plan(scope, plan)


def _grounded(
    document: KnowledgeDocument,
    *,
    answer: str | None = None,
    calls: list[tuple[KnowledgeDocument, ...]] | None = None,
    on_call: Callable[[], None] | None = None,
):
    def generate(question: str, documents: tuple[KnowledgeDocument, ...]) -> dict:
        if calls is not None:
            calls.append(tuple(documents))
        if on_call is not None:
            on_call()
        return {
            "answer": answer if answer is not None else document.body,
            "disposition": "grounded",
            "evidence": [{"document_id": document.document_id, "quote": document.body}],
        }

    return generate


def _encoded(response: dict) -> str:
    return json.dumps(response, default=str)


def _assert_absent(response: dict, *secrets: str) -> None:
    encoded = _encoded(response)
    for secret in secrets:
        assert secret not in encoded, secret


def _assert_shape(response: dict) -> None:
    assert set(response) >= {"answer", "disposition", "evidence", "cache_hit"}
    assert isinstance(response["cache_hit"], bool)
    assert response["disposition"] in {"grounded", "insufficient_evidence"}
    assert isinstance(response["answer"], str)
    assert isinstance(response["evidence"], list)
    if response["disposition"] == "grounded":
        assert response["evidence"]


def test_state_is_empty_for_an_unknown_source(store: SQLiteBrainStore) -> None:
    state = store.state(TENANT_A, "confluence:never-synced")
    assert state.generation == 0
    assert state.source_id == ""
    assert state.cursor is None


def test_two_tenants_with_duplicate_provider_ids_stay_isolated(
    store: SQLiteBrainStore,
) -> None:
    doc_a = _document("page:refunds", FINANCE_SECRET, acl=_acl("finance"))
    doc_b = _document("page:refunds", SUPPORT_SECRET, acl=_acl("support"))
    assert doc_a.document_id == doc_b.document_id
    _apply_full(store, TENANT_A, (doc_a,))
    _apply_full(store, TENANT_B, (doc_b,))

    assert [row.body for row in store.documents(TENANT_A)] == [FINANCE_SECRET]
    assert [row.body for row in store.documents(TENANT_B)] == [SUPPORT_SECRET]
    assert store.get_document(TENANT_A, doc_a.document_id).body == FINANCE_SECRET
    assert store.get_document(TENANT_B, doc_b.document_id).body == SUPPORT_SECRET
    assert store.projection(TENANT_A)[doc_a.document_id] == FINANCE_SECRET
    assert store.projection(TENANT_B)[doc_b.document_id] == SUPPORT_SECRET

    store.set_groups(TENANT_A, "alice", ["finance"])
    store.set_groups(TENANT_B, "bob", ["support"])
    brain_a = CompanyBrain(store, TENANT_A)
    brain_b = CompanyBrain(store, TENANT_B)

    hits_a = brain_a.search(FINANCE_QUESTION, user_id="alice")
    hits_b = brain_b.search(SUPPORT_QUESTION, user_id="bob")
    assert FINANCE_SECRET in _encoded({"hits": [row.body for row in hits_a]})
    assert SUPPORT_SECRET not in _encoded({"hits": [row.body for row in hits_a]})
    assert SUPPORT_SECRET in _encoded({"hits": [row.body for row in hits_b]})
    assert FINANCE_SECRET not in _encoded({"hits": [row.body for row in hits_b]})

    response_a = brain_a.answer(FINANCE_QUESTION, user_id="alice")
    response_b = brain_b.answer(SUPPORT_QUESTION, user_id="bob")
    _assert_absent(response_a, SUPPORT_SECRET)
    _assert_absent(response_b, FINANCE_SECRET)


def test_search_hides_restricted_documents_until_group_membership(
    store: SQLiteBrainStore,
) -> None:
    public = _document("page:public", PUBLIC_BODY)
    hidden = _document("page:hidden", HIDDEN_SECRET, acl=_acl("secret-team"))
    _apply_full(store, TENANT_A, (public, hidden))
    brain = CompanyBrain(store, TENANT_A)

    before = brain.search(HIDDEN_QUESTION, user_id="carol")
    assert all(HIDDEN_SECRET not in row.body for row in before)

    store.set_groups(TENANT_A, "dave", ["secret-team"])
    after = brain.search(HIDDEN_QUESTION, user_id="dave")
    assert any(HIDDEN_SECRET in row.body for row in after)


def test_cached_answer_revoked_by_same_revision_acl_change(
    store: SQLiteBrainStore,
) -> None:
    doc = _document("page:refunds", FINANCE_SECRET, acl=_acl("finance"))
    _apply_full(store, TENANT_A, (doc,))
    store.set_groups(TENANT_A, "alice", ["finance"])
    brain = CompanyBrain(store, TENANT_A)

    cold = brain.answer(FINANCE_QUESTION, user_id="alice", generate=_grounded(doc))
    assert cold["disposition"] == "grounded"
    assert cold["cache_hit"] is False
    assert FINANCE_SECRET in _encoded(cold)

    warm = brain.answer(FINANCE_QUESTION, user_id="alice")
    assert warm["cache_hit"] is True
    assert FINANCE_SECRET in _encoded(warm)

    moved = _document("page:refunds", FINANCE_SECRET, revision="r1", acl=_acl("legal"))
    _apply_change(store, TENANT_A, upserts=(moved,))
    reread = store.get_document(TENANT_A, doc.document_id)
    assert reread is not None and reread.revision == "r1"
    assert reread.acl == _acl("legal")

    revoked = brain.answer(FINANCE_QUESTION, user_id="alice")
    _assert_shape(revoked)
    _assert_absent(revoked, FINANCE_SECRET)
    assert revoked["cache_hit"] is False
    assert revoked["disposition"] == "insufficient_evidence"


def test_group_removal_revokes_a_cached_answer(store: SQLiteBrainStore) -> None:
    doc = _document("page:refunds", FINANCE_SECRET, acl=_acl("finance"))
    _apply_full(store, TENANT_A, (doc,))
    store.set_groups(TENANT_A, "alice", ["finance"])
    brain = CompanyBrain(store, TENANT_A)

    assert (
        brain.answer(FINANCE_QUESTION, user_id="alice", generate=_grounded(doc))[
            "disposition"
        ]
        == "grounded"
    )
    assert brain.answer(FINANCE_QUESTION, user_id="alice")["cache_hit"] is True

    store.set_groups(TENANT_A, "alice", [])
    revoked = brain.answer(FINANCE_QUESTION, user_id="alice")
    _assert_absent(revoked, FINANCE_SECRET)
    assert revoked["cache_hit"] is False
    assert revoked["disposition"] == "insufficient_evidence"


def test_public_to_restricted_change_revokes_a_cached_answer(
    store: SQLiteBrainStore,
) -> None:
    doc = _document("page:public", PUBLIC_BODY)
    _apply_full(store, TENANT_A, (doc,))
    brain = CompanyBrain(store, TENANT_A)

    cold = brain.answer(PUBLIC_QUESTION, user_id="carol", generate=_grounded(doc))
    assert cold["disposition"] == "grounded"
    assert brain.answer(PUBLIC_QUESTION, user_id="carol")["cache_hit"] is True

    restricted = _document("page:public", PUBLIC_BODY, revision="r1", acl=_acl("legal"))
    _apply_change(store, TENANT_A, upserts=(restricted,))

    revoked = brain.answer(PUBLIC_QUESTION, user_id="carol")
    _assert_absent(revoked, PUBLIC_BODY)
    assert revoked["cache_hit"] is False
    assert revoked["disposition"] == "insufficient_evidence"


def test_deletion_revokes_a_cached_answer_and_live_reads(
    store: SQLiteBrainStore,
) -> None:
    doc = _document("page:refunds", FINANCE_SECRET, acl=_acl("finance"))
    _apply_full(store, TENANT_A, (doc,))
    store.set_groups(TENANT_A, "alice", ["finance"])
    brain = CompanyBrain(store, TENANT_A)

    assert (
        brain.answer(FINANCE_QUESTION, user_id="alice", generate=_grounded(doc))[
            "disposition"
        ]
        == "grounded"
    )
    assert brain.answer(FINANCE_QUESTION, user_id="alice")["cache_hit"] is True

    _apply_change(
        store,
        TENANT_A,
        tombstones=(Tombstone(source_id=SOURCE, external_id="page:refunds"),),
    )
    assert store.get_document(TENANT_A, doc.document_id) is None
    assert store.documents(TENANT_A) == ()
    assert store.projection(TENANT_A) == {}
    assert brain.search(FINANCE_QUESTION, user_id="alice") == ()

    revoked = brain.answer(FINANCE_QUESTION, user_id="alice")
    _assert_absent(revoked, FINANCE_SECRET)
    assert revoked["cache_hit"] is False
    assert revoked["disposition"] == "insufficient_evidence"


def test_callback_revoking_the_group_during_generation_is_not_served(
    store: SQLiteBrainStore,
) -> None:
    doc = _document("page:refunds", FINANCE_SECRET, acl=_acl("finance"))
    _apply_full(store, TENANT_A, (doc,))
    store.set_groups(TENANT_A, "alice", ["finance"])
    brain = CompanyBrain(store, TENANT_A)
    calls: list[tuple[KnowledgeDocument, ...]] = []

    generate = _grounded(
        doc,
        calls=calls,
        on_call=lambda: store.set_groups(TENANT_A, "alice", []),
    )
    response = brain.answer(FINANCE_QUESTION, user_id="alice", generate=generate)
    assert calls
    _assert_absent(response, FINANCE_SECRET)
    assert response["cache_hit"] is False

    followup = brain.answer(FINANCE_QUESTION, user_id="alice")
    _assert_absent(followup, FINANCE_SECRET)
    assert followup["cache_hit"] is False
    assert store.groups(TENANT_A, "alice") == frozenset()


def test_callback_editing_the_source_during_generation_never_serves_old_prose(
    store: SQLiteBrainStore,
) -> None:
    original = _document("page:refunds", FINANCE_SECRET, acl=_acl("finance"))
    updated = _document(
        "page:refunds", UPDATED_FINANCE_SECRET, revision="r2", acl=_acl("finance")
    )
    _apply_full(store, TENANT_A, (original,))
    store.set_groups(TENANT_A, "alice", ["finance"])
    brain = CompanyBrain(store, TENANT_A)

    def generate(question: str, documents: tuple[KnowledgeDocument, ...]) -> dict:
        _apply_change(store, TENANT_A, upserts=(updated,))
        return {
            "answer": FINANCE_SECRET,
            "disposition": "grounded",
            "evidence": [
                {"document_id": original.document_id, "quote": FINANCE_SECRET}
            ],
        }

    response = brain.answer(FINANCE_QUESTION, user_id="alice", generate=generate)
    _assert_shape(response)
    _assert_absent(response, FINANCE_SECRET)
    assert response["cache_hit"] is False
    assert store.get_document(TENANT_A, original.document_id).body == (
        UPDATED_FINANCE_SECRET
    )


def test_mixed_authorized_and_hidden_citations_never_leak_hidden_text(
    store: SQLiteBrainStore,
) -> None:
    public = _document("page:public", PUBLIC_BODY)
    hidden = _document("page:hidden", HIDDEN_SECRET, acl=_acl("secret-team"))
    _apply_full(store, TENANT_A, (public, hidden))
    brain = CompanyBrain(store, TENANT_A)
    calls: list[tuple[KnowledgeDocument, ...]] = []

    def generate(question: str, documents: tuple[KnowledgeDocument, ...]) -> dict:
        calls.append(tuple(documents))
        return {
            "answer": f"{HIDDEN_SECRET} {PUBLIC_BODY}",
            "disposition": "grounded",
            "evidence": [
                {"document_id": hidden.document_id, "quote": HIDDEN_SECRET},
                {"document_id": public.document_id, "quote": PUBLIC_BODY},
            ],
        }

    response = brain.answer(PUBLIC_QUESTION, user_id="carol", generate=generate)
    _assert_shape(response)
    _assert_absent(response, HIDDEN_SECRET)
    assert calls
    assert all(HIDDEN_SECRET not in row.body for row in calls[0])
    assert any(PUBLIC_BODY in row.body for row in calls[0])


def test_uncited_hidden_citation_from_a_callback_is_rejected(
    store: SQLiteBrainStore,
) -> None:
    public = _document("page:public", PUBLIC_BODY)
    hidden = _document("page:hidden", HIDDEN_SECRET, acl=_acl("secret-team"))
    _apply_full(store, TENANT_A, (public, hidden))
    brain = CompanyBrain(store, TENANT_A)

    def generate(question: str, documents: tuple[KnowledgeDocument, ...]) -> dict:
        return {
            "answer": HIDDEN_SECRET,
            "disposition": "grounded",
            "evidence": [{"document_id": hidden.document_id, "quote": HIDDEN_SECRET}],
        }

    response = brain.answer(HIDDEN_QUESTION, user_id="carol", generate=generate)
    _assert_shape(response)
    _assert_absent(response, HIDDEN_SECRET)
    if response["disposition"] == "grounded":
        assert all(
            row.get("document_id") != hidden.document_id for row in response["evidence"]
        )


def test_authorized_user_keeps_working_after_another_user_is_revoked(
    store: SQLiteBrainStore,
) -> None:
    doc = _document("page:refunds", FINANCE_SECRET, acl=_acl("finance"))
    _apply_full(store, TENANT_A, (doc,))
    store.set_groups(TENANT_A, "alice", ["finance"])
    store.set_groups(TENANT_A, "bob", ["finance"])
    brain = CompanyBrain(store, TENANT_A)

    assert (
        brain.answer(FINANCE_QUESTION, user_id="alice", generate=_grounded(doc))[
            "disposition"
        ]
        == "grounded"
    )
    store.set_groups(TENANT_A, "alice", [])

    still_authorized = brain.answer(FINANCE_QUESTION, user_id="bob")
    assert still_authorized["disposition"] == "grounded"
    assert FINANCE_SECRET in _encoded(still_authorized)

    revoked = brain.answer(FINANCE_QUESTION, user_id="alice")
    _assert_absent(revoked, FINANCE_SECRET)
    assert revoked["disposition"] == "insufficient_evidence"


def test_access_snapshot_reports_live_documents_and_groups(
    store: SQLiteBrainStore,
) -> None:
    public = _document("page:public", PUBLIC_BODY)
    hidden = _document("page:hidden", HIDDEN_SECRET, acl=_acl("secret-team"))
    _apply_full(store, TENANT_A, (public, hidden))
    store.set_groups(TENANT_A, "dave", ["secret-team"])

    documents, groups = store.access_snapshot(TENANT_A, "dave")
    assert {row.document_id for row in documents} == {
        public.document_id,
        hidden.document_id,
    }
    assert groups == frozenset({"secret-team"})

    restricted = _document(
        "page:hidden", HIDDEN_SECRET, revision="r1", acl=_acl("legal")
    )
    _apply_change(store, TENANT_A, upserts=(restricted,))
    store.set_groups(TENANT_A, "dave", [])
    documents_after, groups_after = store.access_snapshot(TENANT_A, "dave")
    reread = next(
        row for row in documents_after if row.document_id == hidden.document_id
    )
    assert reread.acl == _acl("legal")
    assert groups_after == frozenset()


def test_cache_and_projection_are_scope_isolated(store: SQLiteBrainStore) -> None:
    doc_a = _document("page:shared", FINANCE_SECRET, acl=_acl("finance"))
    doc_b = _document("page:shared", SUPPORT_SECRET, acl=_acl("support"))
    _apply_full(store, TENANT_A, (doc_a,))
    _apply_full(store, TENANT_B, (doc_b,))

    store.save_cache(TENANT_A, "question", {"answer": FINANCE_SECRET})
    store.save_cache(TENANT_B, "question", {"answer": SUPPORT_SECRET})
    assert store.load_cache(TENANT_A, "question") == {"answer": FINANCE_SECRET}
    assert store.load_cache(TENANT_B, "question") == {"answer": SUPPORT_SECRET}
    assert store.load_cache(TENANT_A, "never-stored") is None

    assert doc_a.document_id == doc_b.document_id
    assert store.projection(TENANT_A)[doc_a.document_id] == FINANCE_SECRET
    assert store.projection(TENANT_B)[doc_b.document_id] == SUPPORT_SECRET


def test_a_second_store_instance_observes_commits_and_revocations(
    tmp_path: Path,
) -> None:
    path = str(tmp_path / "shared.sqlite3")
    scope = TENANT_A
    writer = SQLiteBrainStore(path)
    try:
        doc = _document("page:refunds", FINANCE_SECRET, acl=_acl("finance"))
        _apply_full(writer, scope, (doc,))
        writer.set_groups(scope, "alice", ["finance"])

        reader = SQLiteBrainStore(path)
        try:
            live = reader.get_document(scope, doc.document_id)
            assert live is not None and live.body == FINANCE_SECRET
            assert reader.groups(scope, "alice") == frozenset({"finance"})

            brain = CompanyBrain(reader, scope)
            warm = brain.answer(
                FINANCE_QUESTION, user_id="alice", generate=_grounded(doc)
            )
            assert warm["disposition"] == "grounded"
            assert FINANCE_SECRET in _encoded(warm)

            moved = _document(
                "page:refunds", FINANCE_SECRET, revision="r1", acl=_acl("legal")
            )
            _apply_change(writer, scope, upserts=(moved,))
            revoked = brain.answer(FINANCE_QUESTION, user_id="alice")
            _assert_absent(revoked, FINANCE_SECRET)
            assert revoked["cache_hit"] is False
        finally:
            reader.close()
    finally:
        writer.close()


def test_stale_generation_plan_is_rejected_without_partial_writes(
    store: SQLiteBrainStore,
) -> None:
    first = _document("page:refunds", FINANCE_SECRET, acl=_acl("finance"))
    _apply_full(store, TENANT_A, (first,))

    stale_state = store.state(TENANT_A, SOURCE)
    stale = plan_sync(
        stale_state,
        PollPage(
            upserts=(
                _document(
                    "page:refunds",
                    UPDATED_FINANCE_SECRET,
                    revision="r2",
                    acl=_acl("finance"),
                ),
            ),
            snapshot_complete=True,
        ),
        source_id=SOURCE,
        mode=SyncMode.INCREMENTAL,
    )

    accepted_state = store.state(TENANT_A, SOURCE)
    accepted = plan_sync(
        accepted_state,
        PollPage(
            upserts=(
                _document(
                    "page:refunds",
                    SUPPORT_SECRET,
                    revision="r3",
                    acl=_acl("finance"),
                ),
            ),
            snapshot_complete=True,
        ),
        source_id=SOURCE,
        mode=SyncMode.INCREMENTAL,
    )
    store.apply_plan(TENANT_A, accepted)

    with pytest.raises((ValueError, RuntimeError)):
        store.apply_plan(TENANT_A, stale)
    assert store.get_document(TENANT_A, first.document_id).body == SUPPORT_SECRET


def test_a_plan_built_for_one_scope_cannot_write_into_another(
    store: SQLiteBrainStore,
) -> None:
    first = _document("page:refunds", FINANCE_SECRET, acl=_acl("finance"))
    _apply_full(store, TENANT_A, (first,))

    state_a = store.state(TENANT_A, SOURCE)
    plan_a = plan_sync(
        state_a,
        PollPage(
            upserts=(
                _document(
                    "page:refunds",
                    UPDATED_FINANCE_SECRET,
                    revision="r2",
                    acl=_acl("finance"),
                ),
            ),
            snapshot_complete=True,
        ),
        source_id=SOURCE,
        mode=SyncMode.INCREMENTAL,
    )
    assert plan_a.expected_generation == 1

    with pytest.raises((ValueError, RuntimeError)):
        store.apply_plan(TENANT_B, plan_a)
    assert store.documents(TENANT_B) == ()
    assert store.state(TENANT_B, SOURCE).generation == 0


def test_edit_invalidates_a_cached_answer_even_when_still_authorized(
    store: SQLiteBrainStore,
) -> None:
    doc = _document("page:public", PUBLIC_BODY)
    _apply_full(store, TENANT_A, (doc,))
    brain = CompanyBrain(store, TENANT_A)
    assert (
        brain.answer(PUBLIC_QUESTION, user_id="carol", generate=_grounded(doc))[
            "disposition"
        ]
        == "grounded"
    )

    updated = _document("page:public", FINANCE_SECRET, revision="r2")
    _apply_change(store, TENANT_A, upserts=(updated,))
    refreshed = brain.answer(PUBLIC_QUESTION, user_id="carol")
    _assert_absent(refreshed, PUBLIC_BODY)
    assert refreshed["cache_hit"] is False
