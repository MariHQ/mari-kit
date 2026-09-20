"""Behavioral tests for the durable, permission-aware company brain engine.

Owned by the wave-2 permission builder. These tests exercise ``CompanyBrain``
against the real ``SQLiteBrainStore``: explicit host ACL policy, per-request
authorization reads, persisted answer caching, callback validation,
revalidation after generation, and invalidation by edits, deletes,
same-revision ACL changes, and group membership changes. Every assertion follows
the Wave 2 shared contract.
"""

from __future__ import annotations

from dataclasses import replace

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

SOURCE = "handbook"
SCOPE = ScopeRef(tenant="wave2-engine", space="company")
QUESTION = "What is the refund window?"
QUERY = "refund window"
SUPPORT = Principal(kind="team", identifier="support")


def document(
    external_id: str,
    body: str,
    revision: str,
    *,
    title: str = "Refund policy",
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


SUPPORT_POLICY = document("refunds", "The refund window is 30 days.", "v1")
PUBLIC_NEWS = document(
    "onboarding",
    "New employees attend orientation on Monday.",
    "v1",
    title="Onboarding",
    visibility="public",
)


def sync_full(store: SQLiteBrainStore, *documents: KnowledgeDocument) -> None:
    plan = plan_sync(
        store.state(SCOPE, SOURCE),
        PollPage(upserts=tuple(documents), snapshot_complete=True),
        source_id=SOURCE,
        mode=SyncMode.FULL,
    )
    store.apply_plan(SCOPE, plan)


def sync_incremental(
    store: SQLiteBrainStore,
    *,
    upserts: tuple[KnowledgeDocument, ...] = (),
    tombstones: tuple[Tombstone, ...] = (),
) -> None:
    plan = plan_sync(
        store.state(SCOPE, SOURCE),
        PollPage(upserts=upserts, tombstones=tombstones, snapshot_complete=True),
        source_id=SOURCE,
        mode=SyncMode.INCREMENTAL,
    )
    store.apply_plan(SCOPE, plan)


def test_search_applies_explicit_host_policy(tmp_path: object) -> None:
    path = str(tmp_path)
    with SQLiteBrainStore(path) as store:
        sync_full(store, SUPPORT_POLICY, PUBLIC_NEWS)
        store.set_groups(SCOPE, "member", {"support"})
        store.set_groups(SCOPE, "outsider", set())
        brain = CompanyBrain(store, SCOPE)

        member_hits = brain.search(QUERY, user_id="member")
        outsider_hits = brain.search(QUERY, user_id="outsider")

        assert member_hits == (SUPPORT_POLICY,)
        assert outsider_hits == ()
        # Public documents remain tenant-visible for other queries.
        assert {
            row.document_id for row in brain.search("orientation", user_id="outsider")
        } == {PUBLIC_NEWS.document_id}


def test_answer_grounds_and_reuses_persisted_cache(tmp_path: object) -> None:
    path = str(tmp_path)
    with SQLiteBrainStore(path) as store:
        sync_full(store, SUPPORT_POLICY, PUBLIC_NEWS)
        store.set_groups(SCOPE, "alice", {"support"})
        brain = CompanyBrain(store, SCOPE)

        first = brain.answer(QUESTION, user_id="alice")
        second = brain.answer(QUESTION, user_id="alice")

        assert first["disposition"] == "grounded"
        assert first["cache_hit"] is False
        assert "30 days" in first["answer"]
        assert first["evidence"] == [
            {
                "document_id": SUPPORT_POLICY.document_id,
                "revision": "v1",
                "quote": "The refund window is 30 days.",
                "section_id": "root",
                "start": 0,
                "end": 29,
            }
        ]
        assert second["cache_hit"] is True
        assert second["answer"] == first["answer"]

    with SQLiteBrainStore(path) as reopened:
        restarted = CompanyBrain(reopened, SCOPE).answer(QUESTION, user_id="alice")
        assert restarted["cache_hit"] is True
        assert restarted["answer"] == first["answer"]


def test_group_revocation_blocks_cached_answer(tmp_path: object) -> None:
    path = str(tmp_path)
    with SQLiteBrainStore(path) as store:
        sync_full(store, SUPPORT_POLICY, PUBLIC_NEWS)
        store.set_groups(SCOPE, "alice", {"support"})
        brain = CompanyBrain(store, SCOPE)
        assert brain.answer(QUESTION, user_id="alice")["disposition"] == "grounded"

        store.set_groups(SCOPE, "alice", set())
        revoked = brain.answer(QUESTION, user_id="alice")

        assert revoked["disposition"] == "insufficient_evidence"
        assert revoked["cache_hit"] is False
        assert "30 days" not in revoked["answer"]


def test_group_grant_enables_newly_authorized_user(tmp_path: object) -> None:
    path = str(tmp_path)
    with SQLiteBrainStore(path) as store:
        sync_full(store, SUPPORT_POLICY, PUBLIC_NEWS)
        store.set_groups(SCOPE, "carol", set())
        brain = CompanyBrain(store, SCOPE)
        denied = brain.answer(QUESTION, user_id="carol")
        assert denied["disposition"] == "insufficient_evidence"

        store.set_groups(SCOPE, "carol", {"support"})
        granted = brain.answer(QUESTION, user_id="carol")

        assert granted["disposition"] == "grounded"
        assert "30 days" in granted["answer"]


def test_user_principal_grants_restricted_document(tmp_path: object) -> None:
    path = str(tmp_path)
    personal = document(
        "refunds",
        "The refund window is 30 days.",
        "v1",
        principals=(Principal(kind="user", identifier="alice"),),
    )
    with SQLiteBrainStore(path) as store:
        sync_full(store, personal, PUBLIC_NEWS)
        store.set_groups(SCOPE, "alice", set())
        brain = CompanyBrain(store, SCOPE)

        assert brain.search(QUERY, user_id="alice") == (personal,)
        assert brain.answer(QUESTION, user_id="alice")["disposition"] == "grounded"
        assert (
            brain.answer(QUESTION, user_id="bob")["disposition"]
            == "insufficient_evidence"
        )


def test_edit_invalidates_cached_answer(tmp_path: object) -> None:
    path = str(tmp_path)
    with SQLiteBrainStore(path) as store:
        sync_full(store, SUPPORT_POLICY, PUBLIC_NEWS)
        store.set_groups(SCOPE, "bob", {"support"})
        brain = CompanyBrain(store, SCOPE)
        assert "30 days" in brain.answer(QUESTION, user_id="bob")["answer"]

        revised = replace(
            SUPPORT_POLICY,
            body="The refund window is 45 days.",
            revision="v2",
            content_digest="",
        )
        sync_incremental(store, upserts=(revised,))
        edited = brain.answer(QUESTION, user_id="bob")

        assert edited["cache_hit"] is False
        assert "45 days" in edited["answer"]
        assert "30 days" not in edited["answer"]


def test_delete_invalidates_cached_answer(tmp_path: object) -> None:
    path = str(tmp_path)
    with SQLiteBrainStore(path) as store:
        sync_full(store, SUPPORT_POLICY, PUBLIC_NEWS)
        store.set_groups(SCOPE, "bob", {"support"})
        brain = CompanyBrain(store, SCOPE)
        assert brain.answer(QUESTION, user_id="bob")["disposition"] == "grounded"

        sync_incremental(
            store,
            tombstones=(Tombstone(source_id=SOURCE, external_id="refunds"),),
        )
        deleted = brain.answer(QUESTION, user_id="bob")

        assert deleted["disposition"] == "insufficient_evidence"
        assert deleted["cache_hit"] is False
        assert "30 days" not in deleted["answer"]


def test_same_revision_acl_change_blocks_cached_answer(tmp_path: object) -> None:
    path = str(tmp_path)
    with SQLiteBrainStore(path) as store:
        sync_full(store, SUPPORT_POLICY, PUBLIC_NEWS)
        store.set_groups(SCOPE, "bob", {"support"})
        store.set_groups(SCOPE, "carol", {"finance"})
        brain = CompanyBrain(store, SCOPE)
        assert brain.answer(QUESTION, user_id="bob")["disposition"] == "grounded"

        reobserved = replace(
            SUPPORT_POLICY,
            content_digest="",
            acl=DocumentACL(
                visibility="restricted",
                principals=(Principal(kind="team", identifier="finance"),),
            ),
        )
        assert reobserved.revision == SUPPORT_POLICY.revision
        sync_incremental(store, upserts=(reobserved,))

        revoked = brain.answer(QUESTION, user_id="bob")
        assert revoked["disposition"] == "insufficient_evidence"
        assert revoked["cache_hit"] is False

        granted = brain.answer(QUESTION, user_id="carol")
        assert granted["disposition"] == "grounded"
        assert "30 days" in granted["answer"]


def test_callback_cannot_cite_hidden_source(tmp_path: object) -> None:
    path = str(tmp_path)
    calls: list[int] = []
    with SQLiteBrainStore(path) as store:
        sync_full(store, SUPPORT_POLICY, PUBLIC_NEWS)
        store.set_groups(SCOPE, "outsider", set())
        brain = CompanyBrain(store, SCOPE)

        def hidden(question: str, documents: tuple[KnowledgeDocument, ...]) -> dict:
            calls.append(len(documents))
            return {
                "answer": "The refund window is 30 days.",
                "disposition": "grounded",
                "evidence": [
                    {
                        "document_id": SUPPORT_POLICY.document_id,
                        "quote": "The refund window is 30 days.",
                    }
                ],
            }

        result = brain.answer(QUESTION, user_id="outsider", generate=hidden)
        assert result["disposition"] == "insufficient_evidence"
        assert result["cache_hit"] is False
        assert "30 days" not in result["answer"]

        # Malformed output is never cached, so a corrected callback can retry.
        brain.answer(QUESTION, user_id="outsider", generate=hidden)
        assert len(calls) == 2


def test_callback_race_never_serves_pre_edit_prose(tmp_path: object) -> None:
    path = str(tmp_path)
    applied: list[bool] = []
    with SQLiteBrainStore(path) as store:
        sync_full(store, PUBLIC_NEWS)
        brain = CompanyBrain(store, SCOPE)
        old_quote = PUBLIC_NEWS.body

        def racing(question: str, documents: tuple[KnowledgeDocument, ...]) -> dict:
            if not applied:
                applied.append(True)
                sync_incremental(
                    store,
                    upserts=(
                        replace(
                            PUBLIC_NEWS,
                            body="Orientation moved to Tuesday.",
                            revision="v2",
                            content_digest="",
                        ),
                    ),
                )
            return {
                "answer": old_quote,
                "disposition": "grounded",
                "evidence": [
                    {"document_id": PUBLIC_NEWS.document_id, "quote": old_quote}
                ],
            }

        result = brain.answer("When is orientation?", user_id="anyone", generate=racing)

        assert "Monday" not in result["answer"]
        stored = store.get_document(SCOPE, PUBLIC_NEWS.document_id)
        assert stored is not None and "Tuesday" in stored.body


def test_search_returns_current_revision_after_edit(tmp_path: object) -> None:
    path = str(tmp_path)
    with SQLiteBrainStore(path) as store:
        sync_full(store, SUPPORT_POLICY, PUBLIC_NEWS)
        store.set_groups(SCOPE, "bob", {"support"})
        brain = CompanyBrain(store, SCOPE)

        revised = replace(
            SUPPORT_POLICY,
            body="Refunds are processed within 45 days.",
            revision="v2",
            content_digest="",
        )
        sync_incremental(store, upserts=(revised,))

        assert brain.search(QUERY, user_id="bob") == (revised,)
        assert "45 days" in brain.answer(QUESTION, user_id="bob")["answer"]
