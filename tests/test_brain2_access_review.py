"""Independent access/cache review for the durable company brain (wave 2).

These tests probe the persistent access and cache layer from the outside, using
only the public ``SQLiteBrainStore`` / ``CompanyBrain`` contract:

- cache keys are isolated across tenants and users,
- a long-lived brain observes a source edit made by another connection,
- cached answers rehydrate after a restart on the same database,
- a hostile ``generate`` callback cannot cite a hidden document,
- authorization distinguishes the trusted tenant/user identity from a store
  group grant, and is re-read on every request.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence

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

SOURCE = "handbook:acme"
ACME = ScopeRef(tenant="acme", space="brain")
GLOBEX = ScopeRef(tenant="globex", space="brain")


def make_document(
    external_id: str,
    body: str,
    revision: str,
    *,
    visibility: str = "connector_scope",
    principals: Sequence[Principal] = (),
    title: str | None = None,
    metadata: dict | None = None,
    updated_at: str = "",
) -> KnowledgeDocument:
    return KnowledgeDocument(
        source_id=SOURCE,
        external_id=external_id,
        title=title or external_id.replace("-", " ").title(),
        body=body,
        revision=revision,
        updated_at=updated_at,
        acl=DocumentACL(visibility=visibility, principals=tuple(principals)),
        metadata=metadata or {},
    )


PUBLIC = make_document(
    "public-handbook",
    "Company public handbook: expenses are filed within 30 days.",
    "r1",
    visibility="public",
    title="Public handbook",
)
CONNECTOR = make_document(
    "connector-guide",
    "Company connector guide: deploys happen on Tuesdays.",
    "r1",
    visibility="connector_scope",
    title="Connector guide",
)
USER_ONLY = make_document(
    "alice-review",
    "Company alice review: the private target is forty percent.",
    "r1",
    visibility="restricted",
    principals=(Principal(kind="user", identifier="alice"),),
    title="Alice review",
)
TEAM_ONLY = make_document(
    "security-runbook",
    "Company security runbook: rotate the signing key every 90 days.",
    "r1",
    visibility="restricted",
    principals=(Principal(kind="team", identifier="security"),),
    title="Security runbook",
)


def _seed(
    store: SQLiteBrainStore, scope: ScopeRef, documents: Iterable[KnowledgeDocument]
) -> None:
    state = store.state(scope, SOURCE)
    plan = plan_sync(
        state,
        PollPage(upserts=tuple(documents), snapshot_complete=True),
        source_id=SOURCE,
        mode=SyncMode.FULL,
    )
    store.apply_plan(scope, plan)


def _upsert(
    store: SQLiteBrainStore, scope: ScopeRef, document: KnowledgeDocument
) -> None:
    state = store.state(scope, SOURCE)
    plan = plan_sync(
        state,
        PollPage(upserts=(document,), snapshot_complete=True),
        source_id=SOURCE,
        mode=SyncMode.INCREMENTAL,
    )
    store.apply_plan(scope, plan)


def _search_ids(brain: CompanyBrain, query: str, user_id: str) -> set[str]:
    return {
        document.document_id
        for document in brain.search(query, user_id=user_id, limit=10)
    }


def _evidence_ids(result: dict) -> list[str]:
    return [row["document_id"] for row in result["evidence"]]


def _security_generate(question_text, documents):
    """Model output that grounds on the security runbook when it is visible."""

    for document in documents:
        if document.document_id == TEAM_ONLY.document_id:
            return {
                "answer": "Rotate the signing key every 90 days.",
                "disposition": "grounded",
                "evidence": [
                    {
                        "document_id": document.document_id,
                        "quote": "rotate the signing key every 90 days",
                    }
                ],
            }
    return {
        "answer": "No authorized evidence.",
        "disposition": "insufficient_evidence",
        "evidence": [],
    }


# ---------------------------------------------------------------------------
# Cache key isolation
# ---------------------------------------------------------------------------


def test_store_cache_is_isolated_by_scope(tmp_path):
    path = tmp_path / "brain.sqlite3"
    with SQLiteBrainStore(path) as store:
        store.save_cache(ACME, "same-question", {"answer": "acme"})
        store.save_cache(GLOBEX, "same-question", {"answer": "globex"})
        assert store.load_cache(ACME, "same-question") == {"answer": "acme"}
        assert store.load_cache(GLOBEX, "same-question") == {"answer": "globex"}
        assert store.load_cache(ScopeRef(tenant="other"), "same-question") is None
    # The same scoping must survive a reopen of the durable file.
    with SQLiteBrainStore(path) as store:
        assert store.load_cache(ACME, "same-question") == {"answer": "acme"}
        assert store.load_cache(GLOBEX, "same-question") == {"answer": "globex"}


def test_engine_cache_does_not_leak_across_tenants(tmp_path):
    acme_doc = make_document(
        "refunds",
        "Company refunds for acme close in 30 days.",
        "r1",
        visibility="public",
    )
    globex_doc = make_document(
        "refunds",
        "Company refunds for globex close in 90 days.",
        "r1",
        visibility="public",
    )
    with SQLiteBrainStore(tmp_path / "brain.sqlite3") as store:
        _seed(store, ACME, (acme_doc,))
        _seed(store, GLOBEX, (globex_doc,))
        acme_brain = CompanyBrain(store, ACME)
        globex_brain = CompanyBrain(store, GLOBEX)

        acme = acme_brain.answer("When do refunds close?", user_id="alice")
        globex = globex_brain.answer("When do refunds close?", user_id="bob")

        assert acme["cache_hit"] is False
        assert globex["cache_hit"] is False
        assert "30 days" in acme["answer"]
        assert "90 days" in globex["answer"]
        assert "90 days" not in acme["answer"]
        assert "30 days" not in globex["answer"]


def test_cached_restricted_answer_is_not_served_to_another_user(tmp_path):
    with SQLiteBrainStore(tmp_path / "brain.sqlite3") as store:
        _seed(store, ACME, (PUBLIC, TEAM_ONLY))
        store.set_groups(ACME, "alice", ["security"])
        store.set_groups(ACME, "bob", [])
        brain = CompanyBrain(store, ACME)
        question = "How often do we rotate the signing key?"

        warm = brain.answer(question, user_id="alice", generate=_security_generate)
        assert warm["disposition"] == "grounded"
        assert _evidence_ids(warm) == [TEAM_ONLY.document_id]

        leak = brain.answer(question, user_id="bob", generate=_security_generate)
        assert _evidence_ids(leak) == []
        assert TEAM_ONLY.document_id not in json.dumps(leak["evidence"])
        assert "rotate the signing key" not in leak["answer"]
        assert leak["disposition"] == "insufficient_evidence"


# ---------------------------------------------------------------------------
# Stale source observations across connections
# ---------------------------------------------------------------------------


def test_long_lived_brain_observes_another_connections_edit(tmp_path):
    path = tmp_path / "brain.sqlite3"
    v1 = make_document(
        "refunds", "Company refunds close in 30 days.", "r1", visibility="public"
    )
    v2 = make_document(
        "refunds", "Company refunds close in 60 days.", "r2", visibility="public"
    )
    with SQLiteBrainStore(path) as writer:
        _seed(writer, ACME, (v1,))

    reader = SQLiteBrainStore(path)
    try:
        brain = CompanyBrain(reader, ACME)
        first = brain.answer("How long do refunds close?", user_id="alice")
        assert "30 days" in first["answer"]
        assert first["cache_hit"] is False

        other = SQLiteBrainStore(path)
        try:
            _upsert(other, ACME, v2)
        finally:
            other.close()

        fresh = brain.answer("How long do refunds close?", user_id="alice")
        assert "60 days" in fresh["answer"]
        assert "30 days" not in fresh["answer"]
        assert fresh["cache_hit"] is False

        current = reader.get_document(ACME, v2.document_id)
        assert current is not None
        assert current.revision == "r2"
    finally:
        reader.close()


def test_long_lived_brain_drops_a_deleted_document(tmp_path):
    path = tmp_path / "brain.sqlite3"
    doc = make_document(
        "refunds", "Company refunds close in 30 days.", "r1", visibility="public"
    )
    with SQLiteBrainStore(path) as writer:
        _seed(writer, ACME, (doc,))

    reader = SQLiteBrainStore(path)
    try:
        brain = CompanyBrain(reader, ACME)
        assert (
            "30 days"
            in brain.answer("How long do refunds close?", user_id="alice")["answer"]
        )

        other = SQLiteBrainStore(path)
        try:
            state = other.state(ACME, SOURCE)
            plan = plan_sync(
                state,
                PollPage(
                    tombstones=(Tombstone(source_id=SOURCE, external_id="refunds"),),
                    snapshot_complete=True,
                ),
                source_id=SOURCE,
                mode=SyncMode.INCREMENTAL,
            )
            other.apply_plan(ACME, plan)
        finally:
            other.close()

        after = brain.answer("How long do refunds close?", user_id="alice")
        assert "30 days" not in after["answer"]
        assert after["disposition"] == "insufficient_evidence"
        assert reader.get_document(ACME, doc.document_id) is None
    finally:
        reader.close()


# ---------------------------------------------------------------------------
# Cache rehydration
# ---------------------------------------------------------------------------


def test_cached_answer_rehydrates_after_restart(tmp_path):
    path = tmp_path / "brain.sqlite3"
    public = make_document(
        "refunds", "Company refunds close in 30 days.", "r1", visibility="public"
    )
    calls: list[str] = []

    def generate(question, documents):
        calls.append(question)
        document = next(
            row for row in documents if row.document_id == public.document_id
        )
        return {
            "answer": "Refunds close in 30 days.",
            "disposition": "grounded",
            "evidence": [
                {
                    "document_id": document.document_id,
                    "quote": "refunds close in 30 days",
                }
            ],
        }

    with SQLiteBrainStore(path) as store:
        _seed(store, ACME, (public,))
        brain = CompanyBrain(store, ACME)
        first = brain.answer(
            "When do refunds close?", user_id="alice", generate=generate
        )
        assert first["cache_hit"] is False
        assert first["answer"] == "Refunds close in 30 days."
        assert calls == ["When do refunds close?"]

    with SQLiteBrainStore(path) as store:
        brain = CompanyBrain(store, ACME)
        calls.clear()
        second = brain.answer(
            "When do refunds close?", user_id="alice", generate=generate
        )
        assert second["cache_hit"] is True
        assert second["answer"] == first["answer"]
        assert calls == []


# ---------------------------------------------------------------------------
# Malicious callbacks
# ---------------------------------------------------------------------------


def test_hostile_generate_cannot_cite_a_hidden_document(tmp_path):
    with SQLiteBrainStore(tmp_path / "brain.sqlite3") as store:
        _seed(store, ACME, (PUBLIC, TEAM_ONLY))
        store.set_groups(ACME, "mallory", [])
        brain = CompanyBrain(store, ACME)

        def attack(question, documents):
            return {
                "answer": "Rotate the signing key every 90 days.",
                "disposition": "grounded",
                "evidence": [
                    {
                        "document_id": TEAM_ONLY.document_id,
                        "quote": "rotate the signing key every 90 days",
                    }
                ],
            }

        result = brain.answer(
            "How often do we rotate the signing key?",
            user_id="mallory",
            generate=attack,
        )

        assert result["cache_hit"] is False
        assert TEAM_ONLY.document_id not in json.dumps(result["evidence"])
        assert _evidence_ids(result) == []
        assert "rotate the signing key" not in result["answer"]
        assert result["disposition"] == "insufficient_evidence"


def test_hostile_generate_cannot_smuggle_a_cross_tenant_document(tmp_path):
    with SQLiteBrainStore(tmp_path / "brain.sqlite3") as store:
        _seed(store, ACME, (PUBLIC,))
        _seed(store, GLOBEX, (TEAM_ONLY,))
        brain = CompanyBrain(store, ACME)

        def attack(question, documents):
            return {
                "answer": "Rotate the signing key every 90 days.",
                "disposition": "grounded",
                "evidence": [
                    {
                        "document_id": TEAM_ONLY.document_id,
                        "quote": "rotate the signing key every 90 days",
                    }
                ],
            }

        result = brain.answer(
            "How often do we rotate the signing key?",
            user_id="mallory",
            generate=attack,
        )
        assert TEAM_ONLY.document_id not in json.dumps(result["evidence"])
        assert result["disposition"] == "insufficient_evidence"


# ---------------------------------------------------------------------------
# Trusted tenant/user versus group grant
# ---------------------------------------------------------------------------


def test_tenant_visible_policy_and_trusted_identity_grants(tmp_path):
    with SQLiteBrainStore(tmp_path / "brain.sqlite3") as store:
        _seed(store, ACME, (PUBLIC, CONNECTOR, USER_ONLY, TEAM_ONLY))
        store.set_groups(ACME, "alice", [])
        store.set_groups(ACME, "bob", [])
        brain = CompanyBrain(store, ACME)

        bob = _search_ids(brain, "company", "bob")
        assert PUBLIC.document_id in bob
        assert CONNECTOR.document_id in bob
        assert USER_ONLY.document_id not in bob
        assert TEAM_ONLY.document_id not in bob

        alice = _search_ids(brain, "company", "alice")
        assert USER_ONLY.document_id in alice
        assert TEAM_ONLY.document_id not in alice


def test_group_grant_is_read_from_store_on_every_request(tmp_path):
    with SQLiteBrainStore(tmp_path / "brain.sqlite3") as store:
        _seed(store, ACME, (PUBLIC, TEAM_ONLY))
        store.set_groups(ACME, "alice", [])
        brain = CompanyBrain(store, ACME)
        assert TEAM_ONLY.document_id not in _search_ids(brain, "company", "alice")

        store.set_groups(ACME, "alice", ["security"])
        assert TEAM_ONLY.document_id in _search_ids(brain, "company", "alice")

        store.set_groups(ACME, "alice", [])
        assert TEAM_ONLY.document_id not in _search_ids(brain, "company", "alice")


def test_group_grant_is_confined_to_its_tenant(tmp_path):
    path = tmp_path / "brain.sqlite3"
    with SQLiteBrainStore(path) as store:
        _seed(store, ACME, (PUBLIC,))
        _seed(store, GLOBEX, (TEAM_ONLY,))
        store.set_groups(GLOBEX, "alice", ["security"])
        store.set_groups(ACME, "alice", [])
        acme_brain = CompanyBrain(store, ACME)
        assert TEAM_ONLY.document_id not in _search_ids(acme_brain, "company", "alice")

    with SQLiteBrainStore(path) as store:
        globex_brain = CompanyBrain(store, GLOBEX)
        assert TEAM_ONLY.document_id in _search_ids(globex_brain, "company", "alice")


def test_revoked_group_stops_a_cached_restricted_answer(tmp_path):
    with SQLiteBrainStore(tmp_path / "brain.sqlite3") as store:
        _seed(store, ACME, (PUBLIC, TEAM_ONLY))
        store.set_groups(ACME, "alice", ["security"])
        brain = CompanyBrain(store, ACME)
        question = "How often do we rotate the signing key?"

        warm = brain.answer(question, user_id="alice", generate=_security_generate)
        assert warm["disposition"] == "grounded"

        store.set_groups(ACME, "alice", [])
        after = brain.answer(question, user_id="alice", generate=_security_generate)
        assert after["disposition"] == "insufficient_evidence"
        assert TEAM_ONLY.document_id not in json.dumps(after["evidence"])
        assert "rotate the signing key" not in after["answer"]


def test_same_revision_acl_revoke_invalidates_a_cached_answer(tmp_path):
    with SQLiteBrainStore(tmp_path / "brain.sqlite3") as store:
        _seed(store, ACME, (PUBLIC, TEAM_ONLY))
        store.set_groups(ACME, "alice", ["security"])
        brain = CompanyBrain(store, ACME)
        question = "How often do we rotate the signing key?"

        warm = brain.answer(question, user_id="alice", generate=_security_generate)
        assert warm["disposition"] == "grounded"

        revoked = make_document(
            "security-runbook",
            TEAM_ONLY.body,
            TEAM_ONLY.revision,
            visibility="restricted",
            principals=(),
            title="Security runbook",
        )
        _upsert(store, ACME, revoked)

        after = brain.answer(question, user_id="alice", generate=_security_generate)
        assert after["disposition"] == "insufficient_evidence"
        assert after["cache_hit"] is False
        assert TEAM_ONLY.document_id not in json.dumps(after["evidence"])


def test_principal_kind_is_not_interchangeable_with_identity(tmp_path):
    team_named_alice = make_document(
        "team-named-alice",
        "Company team named alice: classified.",
        "r1",
        visibility="restricted",
        principals=(Principal(kind="team", identifier="alice"),),
    )
    user_named_security = make_document(
        "user-named-security",
        "Company user named security: classified.",
        "r1",
        visibility="restricted",
        principals=(Principal(kind="user", identifier="security"),),
    )
    with SQLiteBrainStore(tmp_path / "brain.sqlite3") as store:
        _seed(store, ACME, (team_named_alice, user_named_security))
        store.set_groups(ACME, "alice", ["security"])
        store.set_groups(ACME, "security", [])
        brain = CompanyBrain(store, ACME)

        alice = _search_ids(brain, "company", "alice")
        assert team_named_alice.document_id not in alice
        assert user_named_security.document_id not in alice

        security = _search_ids(brain, "company", "security")
        assert user_named_security.document_id in security
        assert team_named_alice.document_id not in security


# ---------------------------------------------------------------------------
# Durable read consistency
# ---------------------------------------------------------------------------


def test_state_documents_and_projection_round_trip_after_reopen(tmp_path):
    path = tmp_path / "brain.sqlite3"
    document = make_document(
        "policy",
        "Company policy body.",
        "r1",
        visibility="restricted",
        principals=(Principal(kind="team", identifier="security"),),
        metadata={"owner": "legal"},
        updated_at="2026-01-02T03:04:05Z",
    )
    with SQLiteBrainStore(path) as store:
        _seed(store, ACME, (document,))
        state = store.state(ACME, SOURCE)
        assert state.generation == 1
        manifest = dict(state.manifest)

    with SQLiteBrainStore(path) as store:
        assert store.get_document(ACME, document.document_id) == document
        assert store.projection(ACME) == {document.document_id: document.body}
        restored = store.state(ACME, SOURCE)
        assert restored.generation == 1
        assert dict(restored.manifest) == manifest


def test_access_snapshot_returns_documents_and_memberships(tmp_path):
    with SQLiteBrainStore(tmp_path / "brain.sqlite3") as store:
        _seed(store, ACME, (PUBLIC, TEAM_ONLY))
        store.set_groups(ACME, "alice", ["security"])
        documents, memberships = store.access_snapshot(ACME, "alice")
        assert documents == store.documents(ACME)
        assert memberships == store.groups(ACME, "alice") == frozenset({"security"})
