"""Wave-4 adversarial regression tests for the durable company brain.

These tests attack the host-owned durable auth/cache lifecycle from
``examples/company_brains/durable``.  They are written from the point of view of
a *host* that owns the SQLite file and may therefore observe or corrupt the
persisted answer-cache records; they never modify the engine or store.

The suite fixes three independent oracles and compares the engine against them:

* a fresh, independently authorized read of the SQLite store;
* an independent exact BM25 ranker (``_exact_bm25_ranking``) that reimplements
  the Robertson--Walker formula and the reference tie-breaking;
* an independent cache-key derivation and forged-payload injector.

Coverage:

* a deterministic pseudo-random lifecycle over two SQLite connections, two
  scopes, three users, membership changes, same-revision title/body/ACL edits,
  deletes, additions, rollbacks, and store restarts;
* mutable ``CompanyBrain.scope`` changes that happen *during* generation;
* corrupted or misbound cached records (wrong question/user/schema/fingerprint,
  malformed dependencies/evidence, grounded-without-evidence, invalid
  disposition, wrong evidence revision, and ungrounded answer text).

At the wave-4 start revision (``engine.py`` ``ca5fb794``, schema v1) eleven of
these tests failed: cached records were reused without checking the bound
question/user/scope, malformed ``dependencies``/``evidence`` entries raised
``AttributeError``, grounded records without evidence were served, invalid
dispositions passed through, wrong evidence revisions were served, and poisoned
answer text was returned.  The engine owner subsequently added
``cache_records.py`` (schema v2) with request-identity, structural, and checksum
validation; every test now passes.  ``artifacts/company-brains-wave4/adversarial.md``
records the exact pre-fix observations, the fix, and the residual limits of the
unkeyed checksum.  No source file is edited by this wave.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
from collections import Counter
from collections.abc import Collection, Iterable, Iterator, Mapping
from dataclasses import replace
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
    Tombstone,
)
from mari_kit.json import canonical_json_bytes
from mari_kit.retrieval import RevisionBM25Index
from mari_kit.sync import plan_sync

SOURCE = "wave4:handbook"
SCOPE_A = ScopeRef(tenant="wave4-a", space="brain")
SCOPE_B = ScopeRef(tenant="wave4-b", space="brain")
SCOPES = (SCOPE_A, SCOPE_B)
USERS = ("alice", "bob", "carol")
GROUP_POOL = ("support", "finance", "legal")
QUESTION = "What is the refund window?"
QUERIES = ("refund window", "orientation monday", "zephyr ceiling")
LIMIT = 5

SUPPORT = Principal(kind="team", identifier="support")
FINANCE = Principal(kind="team", identifier="finance")


# --------------------------------------------------------------------------- #
# Independent host oracle
# --------------------------------------------------------------------------- #


def _analyze(text: str) -> list[str]:
    """Same tokenization contract as the library, reimplemented locally."""

    return re.findall(r"\w+", text.casefold())


def _position_key(index: int, count: int) -> str:
    return str(index).zfill(len(str(max(count - 1, 0))))


def _host_allowed(
    document: KnowledgeDocument, *, user_id: str, groups: Collection[str]
) -> bool:
    """A second, independent copy of the documented host ACL policy."""

    acl = document.acl
    if acl.visibility in {"public", "connector_scope"}:
        return True
    for principal in acl.principals:
        if principal.kind == "user" and principal.identifier == user_id:
            return True
        if principal.kind == "team" and principal.identifier in groups:
            return True
    return False


def _authorized(
    documents: Iterable[KnowledgeDocument],
    *,
    user_id: str,
    groups: Collection[str],
) -> tuple[KnowledgeDocument, ...]:
    return tuple(
        document
        for document in documents
        if _host_allowed(document, user_id=user_id, groups=groups)
    )


def _exact_bm25_ranking(
    authorized: tuple[KnowledgeDocument, ...],
    scope: ScopeRef,
    query: str,
    limit: int,
) -> tuple[KnowledgeDocument, ...]:
    """Independent exact BM25 with the reference index's tie-breaking.

    The engine indexes ``f"{title} {body}"`` under ``RevisionRef`` keys and
    hands the library padded positional IDs, so ties break by the sorted
    ``ref.key`` order.  This reimplementation reproduces that exactly without
    calling the retrieval package.
    """

    if limit <= 0 or not authorized:
        return ()
    count = len(authorized)
    ordered = sorted(authorized, key=lambda document: document.ref_in(scope).key)
    tokens = [_analyze(f"{document.title} {document.body}") for document in ordered]
    lengths = [len(row) for row in tokens]
    average = sum(lengths) / count
    document_frequency: Counter[str] = Counter()
    for row in tokens:
        document_frequency.update(set(row))
    inverse = {
        term: math.log(1 + (count - freq + 0.5) / (freq + 0.5))
        for term, freq in document_frequency.items()
    }
    terms = _analyze(query)
    scored: list[tuple[int, float]] = []
    for index, row in enumerate(tokens):
        frequencies = Counter(row)
        score = 0.0
        for term in terms:
            frequency = frequencies[term]
            if not frequency:
                continue
            denominator = frequency + 1.2 * (
                1 - 0.75 + 0.75 * lengths[index] / (average or 1)
            )
            score += inverse.get(term, 0.0) * frequency * (1.2 + 1) / denominator
        scored.append((index, score))
    scored.sort(key=lambda item: (-item[1], _position_key(item[0], count)))
    result: list[KnowledgeDocument] = []
    for index, score in scored:
        if score <= 0.0:
            break
        result.append(ordered[index])
        if len(result) >= limit:
            break
    return tuple(result)


def _oracle_hits(
    store: SQLiteBrainStore,
    scope: ScopeRef,
    query: str,
    user_id: str,
    *,
    limit: int = LIMIT,
) -> tuple[KnowledgeDocument, ...]:
    documents = store.documents(scope)
    groups = store.groups(scope, user_id)
    return _exact_bm25_ranking(
        _authorized(documents, user_id=user_id, groups=groups),
        scope,
        query,
        limit,
    )


def _cache_key(question: str, user_id: str) -> str:
    """Independent derivation of the engine's answer-cache key."""

    payload = canonical_json_bytes({"question": question, "user_id": user_id})
    return "answer:" + hashlib.sha256(payload).hexdigest()


# --------------------------------------------------------------------------- #
# Document and sync helpers
# --------------------------------------------------------------------------- #


def _acl(
    *, visibility: str = "restricted", groups: tuple[str, ...] = ("support",)
) -> DocumentACL:
    return DocumentACL(
        visibility=visibility,
        principals=tuple(Principal(kind="team", identifier=group) for group in groups),
    )


def _document(
    external_id: str,
    body: str,
    *,
    revision: str = "r1",
    title: str | None = None,
    acl: DocumentACL | None = None,
) -> KnowledgeDocument:
    return KnowledgeDocument(
        source_id=SOURCE,
        external_id=external_id,
        title=title or external_id,
        body=body,
        revision=revision,
        acl=acl if acl is not None else _acl(),
    )


def _apply(
    store: SQLiteBrainStore,
    scope: ScopeRef,
    *,
    upserts: tuple[KnowledgeDocument, ...] = (),
    tombstones: tuple[Tombstone, ...] = (),
    failpoint=None,  # type: ignore[no-untyped-def]
) -> None:
    state = store.state(scope, SOURCE)
    plan = plan_sync(
        state,
        PollPage(
            upserts=tuple(upserts),
            tombstones=tuple(tombstones),
            snapshot_complete=True,
        ),
        source_id=SOURCE,
        mode=SyncMode.INCREMENTAL,
    )
    store.apply_plan(scope, plan, failpoint=failpoint)


def _all_known_bodies(store: SQLiteBrainStore, scope: ScopeRef) -> set[str]:
    return {document.body for document in store.documents(scope)}


# --------------------------------------------------------------------------- #
# Forged cache-record helpers
# --------------------------------------------------------------------------- #


def _real_cached_payload(store: SQLiteBrainStore, scope: ScopeRef, key: str) -> dict:
    row = store._connection.execute(  # noqa: SLF001 - host inspection of its DB
        "SELECT payload FROM cache WHERE tenant = ? AND space = ? AND cache_key = ?",
        (*scope.key, key),
    ).fetchone()
    assert row is not None, "expected a persisted cache record"
    return json.loads(row[0])


def _store_payload(
    store: SQLiteBrainStore,
    scope: ScopeRef,
    key: str,
    payload: Mapping,
    *,
    reseal: bool = False,
) -> None:
    """Persist a record, optionally recomputing the corruption checksum.

    ``reseal=True`` models a writer that deliberately recomputes the unkeyed
    checksum after tampering, so the test exercises the validator's structural
    and identity checks rather than only the accidental-corruption checksum.
    """

    record = dict(payload)
    if reseal:
        record = seal_cache_record(record)
    store.save_cache(scope, key, record)


def _mutate(payload: dict, **changes: object) -> dict:
    result = json.loads(json.dumps(payload))
    result.update(changes)
    return result


def _assert_safe_answer(result: Mapping, *, forbidden: Iterable[str] = ()) -> None:
    assert set(result) >= {"answer", "disposition", "evidence", "cache_hit"}
    assert isinstance(result["cache_hit"], bool)
    assert result["disposition"] in {"grounded", "insufficient_evidence"}
    assert isinstance(result["answer"], str)
    assert isinstance(result["evidence"], list)
    if result["disposition"] == "grounded":
        assert result["evidence"], "a grounded answer must cite evidence"
    encoded = json.dumps(result, default=str)
    for text in forbidden:
        assert text not in encoded, f"forbidden text leaked: {text!r}"


# --------------------------------------------------------------------------- #
# Oracle self-check
# --------------------------------------------------------------------------- #


def test_independent_oracle_matches_fresh_library_index(tmp_path: Path) -> None:
    with SQLiteBrainStore(tmp_path / "oracle.sqlite3") as store:
        documents = (
            _document("refunds", "Refund window is thirty days.", revision="r1"),
            _document(
                "orientation",
                "Orientation is on Monday.",
                revision="r2",
                acl=_acl(visibility="public", groups=()),
            ),
            _document(
                "zephyr",
                "The zephyr ceiling is nine.",
                revision="r1",
                acl=_acl(groups=("finance",)),
            ),
        )
        _apply(store, SCOPE_A, upserts=documents)
        store.set_groups(SCOPE_A, "alice", {"support"})
        store.set_groups(SCOPE_A, "bob", {"finance"})

        for user_id in USERS:
            groups = store.groups(SCOPE_A, user_id)
            authorized = _authorized(
                store.documents(SCOPE_A), user_id=user_id, groups=groups
            )
            index = RevisionBM25Index(
                {
                    document.ref_in(SCOPE_A): f"{document.title} {document.body}"
                    for document in authorized
                }
            )
            for query in QUERIES:
                expected = tuple(
                    hit_ref_document
                    for hit in index.search(
                        query,
                        limit=LIMIT,
                        allowed_refs={
                            document.ref_in(SCOPE_A) for document in authorized
                        },
                    )
                    if hit.score > 0.0
                    for hit_ref_document in [
                        next(
                            document
                            for document in authorized
                            if document.ref_in(SCOPE_A) == hit.ref
                        )
                    ]
                )
                assert _oracle_hits(store, SCOPE_A, query, user_id) == expected
                assert expected == _oracle_hits(store, SCOPE_A, query, user_id)


# --------------------------------------------------------------------------- #
# Deterministic randomized lifecycle across two connections and scopes
# --------------------------------------------------------------------------- #


def _run_randomized_lifecycle(tmp_path: Path, seed: int) -> list[str]:
    """Run one seeded lifecycle; return human-readable divergences (may be empty)."""

    rng = random.Random(seed)
    path = tmp_path / f"random-{seed}.sqlite3"
    writer = SQLiteBrainStore(path)
    readers: dict[str, SQLiteBrainStore] = {"reader": SQLiteBrainStore(path)}
    oracles: dict[str, SQLiteBrainStore] = {"oracle": SQLiteBrainStore(path)}

    def reader() -> SQLiteBrainStore:
        return readers["reader"]

    def oracle() -> SQLiteBrainStore:
        return oracles["oracle"]

    brains = {scope.key: CompanyBrain(reader(), scope) for scope in SCOPES}
    documents: dict[tuple[str, str], dict[str, KnowledgeDocument]] = {
        scope.key: {} for scope in SCOPES
    }
    membership: dict[tuple[tuple[str, str], str], set[str]] = {
        (scope.key, user): set() for scope in SCOPES for user in USERS
    }
    revisions: dict[tuple[tuple[str, str], str], int] = {}
    next_external = 0
    divergences: list[str] = []

    def apply(scope: ScopeRef, **changes: object) -> None:
        _apply(writer, scope, **changes)  # type: ignore[arg-type]

    def seed_scope(scope: ScopeRef) -> None:
        nonlocal next_external
        seeded = []
        for index in range(4):
            external_id = f"doc-{next_external}"
            next_external += 1
            visibility = ("restricted", "public", "connector_scope")[index % 3]
            groups = GROUP_POOL[: 1 + index % 3]
            document = _document(
                external_id,
                f"The refund window for {external_id} is {30 + index} days "
                f"in {scope.tenant}.",
                revision="r1",
                title=f"Refund policy {external_id}",
                acl=_acl(visibility=visibility, groups=groups),
            )
            documents[scope.key][external_id] = document
            revisions[(scope.key, external_id)] = 1
            seeded.append(document)
        apply(scope, upserts=tuple(seeded))

    for scope in SCOPES:
        seed_scope(scope)
        for user in USERS:
            first = rng.sample(GROUP_POOL, rng.randrange(len(GROUP_POOL) + 1))
            membership[(scope.key, user)] = set(first)
            writer.set_groups(scope, user, first)

    def restart() -> None:
        readers["reader"].close()
        oracles["oracle"].close()
        readers["reader"] = SQLiteBrainStore(path)
        oracles["oracle"] = SQLiteBrainStore(path)
        for scope in SCOPES:
            brains[scope.key] = CompanyBrain(reader(), scope)

    def record(payload: Mapping[str, object]) -> None:
        divergences.append(json.dumps(payload, default=str, sort_keys=True))

    def check_all(step: int, note: str) -> None:
        if len(divergences) >= 12:
            return
        for scope in SCOPES:
            store = oracle()
            for user in USERS:
                for query in QUERIES:
                    expected = _oracle_hits(store, scope, query, user)
                    actual = brains[scope.key].search(query, user_id=user, limit=LIMIT)
                    if actual != expected:
                        record(
                            {
                                "step": step,
                                "note": note,
                                "scope": scope.key,
                                "user": user,
                                "query": query,
                                "expected": [
                                    [row.document_id, row.revision, row.body]
                                    for row in expected
                                ],
                                "actual": [
                                    [row.document_id, row.revision, row.body]
                                    for row in actual
                                ],
                            }
                        )
                top = _oracle_hits(store, scope, QUESTION, user, limit=1)
                answer = brains[scope.key].answer(QUESTION, user_id=user)
                expected_disposition = "grounded" if top else "insufficient_evidence"
                if answer["disposition"] != expected_disposition:
                    record(
                        {
                            "step": step,
                            "note": note,
                            "scope": scope.key,
                            "user": user,
                            "kind": "disposition",
                            "expected": expected_disposition,
                            "actual": answer["disposition"],
                        }
                    )
                elif expected_disposition == "grounded" and answer["evidence"]:
                    if answer["evidence"][0].get("document_id") != top[0].document_id:
                        record(
                            {
                                "step": step,
                                "note": note,
                                "scope": scope.key,
                                "user": user,
                                "kind": "evidence-document",
                                "expected": top[0].document_id,
                                "actual": answer["evidence"][0].get("document_id"),
                            }
                        )

    check_all(0, "seed")

    steps = 90
    for step in range(1, steps + 1):
        scope = SCOPES[rng.randrange(len(SCOPES))]
        kind = rng.randrange(9)
        existing = sorted(documents[scope.key])
        if kind <= 2 and existing:
            external_id = existing[rng.randrange(len(existing))]
            current = documents[scope.key][external_id]
            number = revisions[(scope.key, external_id)] + 1
            if kind == 0:
                updated = replace(
                    current,
                    body=(
                        f"The refund window for {external_id} is {20 + number * 7} "
                        f"days after edit {number} in {scope.tenant}."
                    ),
                    revision=f"r{number}",
                    content_digest="",
                )
            elif kind == 1:
                updated = replace(
                    current, title=f"Refund policy v{number} for {external_id}"
                )
            else:
                acl = _acl(
                    visibility=("restricted", "public", "connector_scope")[number % 3],
                    groups=(GROUP_POOL[number % 3],),
                )
                updated = replace(current, acl=acl)
            revisions[(scope.key, external_id)] = number
            documents[scope.key][external_id] = updated
            apply(scope, upserts=(updated,))
            note = f"edit-{kind}"
        elif kind == 3 and existing:
            external_id = existing[rng.randrange(len(existing))]
            documents[scope.key].pop(external_id)
            apply(
                scope,
                tombstones=(Tombstone(source_id=SOURCE, external_id=external_id),),
            )
            note = "delete"
        elif kind == 4 or not existing:
            external_id = f"doc-{next_external}"
            next_external += 1
            document = _document(
                external_id,
                f"The orientation for {external_id} is on Monday, slot "
                f"{next_external}.",
                revision="r1",
                title=f"Onboarding {external_id}",
                acl=_acl(
                    visibility=("public", "restricted")[next_external % 2],
                    groups=(GROUP_POOL[next_external % 3],),
                ),
            )
            documents[scope.key][external_id] = document
            revisions[(scope.key, external_id)] = 1
            apply(scope, upserts=(document,))
            note = "add"
        elif kind == 5:
            user = USERS[rng.randrange(len(USERS))]
            target = SCOPES[rng.randrange(len(SCOPES))]
            groups = set(rng.sample(GROUP_POOL, rng.randrange(len(GROUP_POOL) + 1)))
            membership[(target.key, user)] = groups
            writer.set_groups(target, user, sorted(groups))
            note = "membership"
        elif kind == 6 and existing:
            external_id = existing[rng.randrange(len(existing))]
            current = documents[scope.key][external_id]
            before_token = writer.access_token(scope, USERS[0])
            updated = replace(current, title=f"Rolled {external_id}")
            detail: dict[str, object] = {}

            def failpoint(stage: str) -> None:
                if stage == "before_commit":
                    raise RuntimeError("injected rollback")

            try:
                apply(scope, upserts=(updated,), failpoint=failpoint)
            except RuntimeError as error:
                detail["raised"] = str(error)
            if detail.get("raised") != "injected rollback":
                record({"step": step, "note": "rollback", "raised": detail})
            after_token = writer.access_token(scope, USERS[0])
            if after_token != before_token:
                record(
                    {
                        "step": step,
                        "note": "rollback-epoch",
                        "before": before_token,
                        "after": after_token,
                    }
                )
            if writer.get_document(scope, current.document_id) != current:
                record({"step": step, "note": "rollback-body", "id": external_id})
            note = "rollback"
        elif kind == 7:
            other = SCOPES[1] if scope is SCOPES[0] else SCOPES[0]
            other_existing = sorted(documents[other.key])
            if other_existing:
                external_id = other_existing[rng.randrange(len(other_existing))]
                current = documents[other.key][external_id]
                number = revisions[(other.key, external_id)] + 1
                updated = replace(
                    current,
                    body=f"Other scope {other.tenant} says {number} days.",
                    revision=f"r{number}",
                    content_digest="",
                )
                revisions[(other.key, external_id)] = number
                documents[other.key][external_id] = updated
                apply(other, upserts=(updated,))
            note = "other-scope"
        else:
            restart()
            note = "restart"
        check_all(step, note)

    writer.close()
    readers["reader"].close()
    oracles["oracle"].close()
    return divergences


@pytest.mark.parametrize("seed", [1, 7, 13, 42, 99])
def test_randomized_lifecycle_matches_fresh_oracle(tmp_path: Path, seed: int) -> None:
    divergences = _run_randomized_lifecycle(tmp_path, seed)
    assert not divergences, "engine diverged from the fresh host oracle:\n" + "\n".join(
        divergences
    )


def _check_pair(
    store: SQLiteBrainStore,
    brain: CompanyBrain,
    scope: ScopeRef,
    user_id: str,
    *,
    query: str = QUERIES[0],
) -> tuple[KnowledgeDocument, ...]:
    expected = _oracle_hits(store, scope, query, user_id)
    actual = brain.search(query, user_id=user_id, limit=LIMIT)
    assert actual == expected, (
        f"{scope.key}/{user_id}: expected "
        f"{[row.document_id for row in expected]}, got "
        f"{[row.document_id for row in actual]}"
    )
    return expected


def test_scripted_lifecycle_matches_oracle_at_every_step(tmp_path: Path) -> None:
    """Deterministic walk over the exact transition classes the wave targets."""

    path = tmp_path / "scripted.sqlite3"
    writer = SQLiteBrainStore(path)
    reader = SQLiteBrainStore(path)
    oracle = SQLiteBrainStore(path)
    try:
        policy = _document("refunds", "The refund window is 30 days.", revision="r1")
        public = _document(
            "orientation",
            "Orientation is on Monday.",
            revision="r1",
            title="Onboarding",
            acl=_acl(visibility="public", groups=()),
        )
        _apply(writer, SCOPE_A, upserts=(policy, public))
        writer.set_groups(SCOPE_A, "alice", {"support"})
        writer.set_groups(SCOPE_A, "bob", {"finance"})
        brain = CompanyBrain(reader, SCOPE_A)

        _check_pair(oracle, brain, SCOPE_A, "alice")
        _check_pair(oracle, brain, SCOPE_A, "bob")

        # Same-revision body edit through the other connection.
        body_edited = replace(
            policy,
            body="The refund window is 45 days.",
            content_digest="",
        )
        assert body_edited.revision == policy.revision
        _apply(writer, SCOPE_A, upserts=(body_edited,))
        row = brain.answer(QUESTION, user_id="alice")
        assert row["cache_hit"] is False
        assert "45 days" in row["answer"]
        assert _check_pair(oracle, brain, SCOPE_A, "alice")[0].body == body_edited.body

        # Same-revision title edit.
        titled = replace(body_edited, title="Archived refund policy", content_digest="")
        _apply(writer, SCOPE_A, upserts=(titled,))
        assert _check_pair(oracle, brain, SCOPE_A, "alice")[0].title == titled.title

        # Same-revision ACL move from support to finance.
        moved = replace(
            titled,
            content_digest="",
            acl=_acl(groups=("finance",)),
        )
        _apply(writer, SCOPE_A, upserts=(moved,))
        assert "45 days" not in brain.answer(QUESTION, user_id="alice")["answer"]
        assert "45 days" in brain.answer(QUESTION, user_id="bob")["answer"]
        _check_pair(oracle, brain, SCOPE_A, "alice")
        _check_pair(oracle, brain, SCOPE_A, "bob")

        # A rolled-back body edit must leave state and the memoized view intact.
        before = writer.access_token(SCOPE_A, "alice")
        rolled = replace(
            moved,
            body="Rolled back body that must never be served.",
            content_digest="",
        )

        def failpoint(stage: str) -> None:
            if stage == "before_commit":
                raise RuntimeError("injected rollback")

        with pytest.raises(RuntimeError, match="injected rollback"):
            _apply(writer, SCOPE_A, upserts=(rolled,), failpoint=failpoint)
        assert writer.access_token(SCOPE_A, "alice") == before
        assert writer.get_document(SCOPE_A, moved.document_id) == moved
        assert "Rolled back" not in brain.answer(QUESTION, user_id="bob")["answer"]
        _check_pair(oracle, brain, SCOPE_A, "bob")

        # Membership revocation through the second connection.
        writer.set_groups(SCOPE_A, "bob", set())
        assert "45 days" not in brain.answer(QUESTION, user_id="bob")["answer"]
        _check_pair(oracle, brain, SCOPE_A, "bob")
        assert all(
            row.document_id != policy.document_id
            for row in _check_pair(oracle, brain, SCOPE_A, "alice")
        )

        # Deletion then restart.
        _apply(
            writer,
            SCOPE_A,
            tombstones=(Tombstone(source_id=SOURCE, external_id="refunds"),),
        )
        assert all(
            row.document_id != policy.document_id
            for row in _check_pair(oracle, brain, SCOPE_A, "carol")
        )
        reader.close()
        oracle.close()
        reader = SQLiteBrainStore(path)
        oracle = SQLiteBrainStore(path)
        brain = CompanyBrain(reader, SCOPE_A)
        _check_pair(oracle, brain, SCOPE_A, "alice")
        assert brain.search("orientation", user_id="carol") == (public,)
    finally:
        oracle.close()
        reader.close()
        writer.close()


def test_engine_never_returns_unauthorized_documents(tmp_path: Path) -> None:
    """A cross-scope/user snapshot must never surface another caller's corpus."""

    with SQLiteBrainStore(tmp_path / "isolate.sqlite3") as store:
        secret_a = _document(
            "shared",
            "TENANT-A Zephyr ceiling is one million.",
            acl=_acl(groups=("finance",)),
        )
        secret_b = _document(
            "shared",
            "TENANT-B Zephyr ceiling is two million.",
            acl=_acl(groups=("finance",)),
        )
        _apply(store, SCOPE_A, upserts=(secret_a,))
        _apply(store, SCOPE_B, upserts=(secret_b,))
        store.set_groups(SCOPE_A, "alice", {"finance"})
        store.set_groups(SCOPE_B, "bob", {"finance"})

        brain_a = CompanyBrain(store, SCOPE_A)
        brain_b = CompanyBrain(store, SCOPE_B)
        for _ in range(3):
            assert brain_a.search("zephyr ceiling", user_id="alice") == (secret_a,)
            assert brain_b.search("zephyr ceiling", user_id="bob") == (secret_b,)
            assert brain_a.search("zephyr ceiling", user_id="bob") == ()
            assert brain_b.search("zephyr ceiling", user_id="alice") == ()


# --------------------------------------------------------------------------- #
# Mutable scope changes during generation
# --------------------------------------------------------------------------- #


def _two_scope_fixture(
    tmp_path: Path,
) -> tuple[SQLiteBrainStore, KnowledgeDocument, KnowledgeDocument]:
    store = SQLiteBrainStore(tmp_path / "scope.sqlite3")
    body_a = "Scope A says the refund window is thirty days."
    body_b = "Scope B says the refund window is ninety days."
    document_a = _document("refunds", body_a, revision="r1")
    document_b = _document("refunds", body_b, revision="r1")
    _apply(store, SCOPE_A, upserts=(document_a,))
    _apply(store, SCOPE_B, upserts=(document_b,))
    for scope in SCOPES:
        for user in USERS:
            store.set_groups(scope, user, {"support"})
    return store, document_a, document_b


def test_scope_switch_during_generation_never_serves_old_scope_prose(
    tmp_path: Path,
) -> None:
    store, document_a, document_b = _two_scope_fixture(tmp_path)
    try:
        brain = CompanyBrain(store, SCOPE_A)
        switched = {"done": False}

        def generate(question: str, documents: tuple[KnowledgeDocument, ...]) -> dict:
            quote = documents[0].body
            if not switched["done"]:
                switched["done"] = True
                brain.scope = SCOPE_B
            return {
                "answer": quote,
                "disposition": "grounded",
                "evidence": [{"document_id": documents[0].document_id, "quote": quote}],
            }

        result = brain.answer(QUESTION, user_id="alice", generate=generate)
        assert switched["done"] is True
        _assert_safe_answer(result, forbidden=(document_a.body,))
        assert document_b.body in result["answer"]

        # The persisted record must be attributed to the scope that was live
        # when it was served, not the scope the request started under.
        assert store.load_cache(SCOPE_B, _cache_key(QUESTION, "alice")) is not None
        assert store.load_cache(SCOPE_A, _cache_key(QUESTION, "alice")) is None

        # A later request under the original scope must re-read its own corpus.
        brain.scope = SCOPE_A
        reread = brain.answer(QUESTION, user_id="alice")
        _assert_safe_answer(reread, forbidden=(document_b.body,))
        assert document_a.body in reread["answer"]
    finally:
        store.close()


def test_scope_switch_to_empty_during_generation_abstains(
    tmp_path: Path,
) -> None:
    store, document_a, _ = _two_scope_fixture(tmp_path)
    empty = ScopeRef(tenant="wave4-empty", space="brain")
    try:
        brain = CompanyBrain(store, SCOPE_A)
        switched = {"done": False}

        def generate(question: str, documents: tuple[KnowledgeDocument, ...]) -> dict:
            if not switched["done"]:
                switched["done"] = True
                brain.scope = empty
            if not documents:
                return {
                    "answer": "No authorized evidence is available.",
                    "disposition": "insufficient_evidence",
                }
            quote = documents[0].body
            return {
                "answer": quote,
                "disposition": "grounded",
                "evidence": [{"document_id": documents[0].document_id, "quote": quote}],
            }

        result = brain.answer(QUESTION, user_id="alice", generate=generate)
        _assert_safe_answer(result, forbidden=(document_a.body,))
        assert result["disposition"] == "insufficient_evidence"
        assert result["cache_hit"] is False
    finally:
        store.close()


# --------------------------------------------------------------------------- #
# Corrupted and misbound persisted cache records
# --------------------------------------------------------------------------- #


@pytest.fixture
def cached_brain(
    tmp_path: Path,
) -> Iterator[tuple[SQLiteBrainStore, CompanyBrain, str]]:
    store = SQLiteBrainStore(tmp_path / "cache.sqlite3")
    policy = _document("refunds", "The refund window is 30 days.", revision="r1")
    _apply(store, SCOPE_A, upserts=(policy,))
    store.set_groups(SCOPE_A, "alice", {"support"})
    brain = CompanyBrain(store, SCOPE_A)
    warm = brain.answer(QUESTION, user_id="alice")
    assert warm["disposition"] == "grounded"
    yield store, brain, _cache_key(QUESTION, "alice")
    store.close()


def test_wrong_schema_record_is_a_cache_miss(
    cached_brain: tuple[SQLiteBrainStore, CompanyBrain, str],
) -> None:
    store, brain, key = cached_brain
    base = _real_cached_payload(store, SCOPE_A, key)
    _store_payload(
        store, SCOPE_A, key, _mutate(base, schema="other-schema-v9"), reseal=True
    )
    result = brain.answer(QUESTION, user_id="alice")
    _assert_safe_answer(result)
    assert result["cache_hit"] is False
    assert "30 days" in result["answer"]


def test_mismatched_question_record_is_not_served(
    cached_brain: tuple[SQLiteBrainStore, CompanyBrain, str],
) -> None:
    store, brain, key = cached_brain
    base = _real_cached_payload(store, SCOPE_A, key)
    poisoned = _mutate(
        base,
        question="A completely different question?",
        answer="WRONG-QUESTION-ANSWER",
    )
    _store_payload(store, SCOPE_A, key, poisoned, reseal=True)
    result = brain.answer(QUESTION, user_id="alice")
    _assert_safe_answer(result, forbidden=("WRONG-QUESTION-ANSWER",))
    assert result["cache_hit"] is False
    assert "30 days" in result["answer"]


def test_mismatched_user_record_is_not_served(
    cached_brain: tuple[SQLiteBrainStore, CompanyBrain, str],
) -> None:
    store, brain, key = cached_brain
    base = _real_cached_payload(store, SCOPE_A, key)
    poisoned = _mutate(base, user_id="mallory", answer="WRONG-USER-ANSWER")
    _store_payload(store, SCOPE_A, key, poisoned, reseal=True)
    result = brain.answer(QUESTION, user_id="alice")
    _assert_safe_answer(result, forbidden=("WRONG-USER-ANSWER",))
    assert result["cache_hit"] is False
    assert "30 days" in result["answer"]


def test_missing_fingerprint_record_is_not_served(
    tmp_path: Path,
) -> None:
    """A re-sealed record without a fingerprint must not match an empty set."""

    with SQLiteBrainStore(tmp_path / "nofp.sqlite3") as store:
        _apply(store, SCOPE_A, upserts=())
        store.set_groups(SCOPE_A, "nobody", set())
        brain = CompanyBrain(store, SCOPE_A)
        key = _cache_key(QUESTION, "nobody")
        # A real abstention establishes the schema/fields for this engine.
        genuine = brain.answer(QUESTION, user_id="nobody")
        assert genuine["disposition"] == "insufficient_evidence"
        base = _real_cached_payload(store, SCOPE_A, key)
        forged = _mutate(base)
        forged.pop("authorized_fingerprint", None)
        forged["answer"] = "FORGED-UNGROUNDED-ANSWER"
        _store_payload(store, SCOPE_A, key, forged, reseal=True)
        result = brain.answer(QUESTION, user_id="nobody")
        _assert_safe_answer(result, forbidden=("FORGED-UNGROUNDED-ANSWER",))
        assert result["cache_hit"] is False
        assert result["disposition"] == "insufficient_evidence"


def test_mismatched_scope_record_is_not_served(tmp_path: Path) -> None:
    """A re-sealed record bound to another scope must be rejected."""

    path = tmp_path / "scope-bind.sqlite3"
    with SQLiteBrainStore(path) as store:
        shared = _document("refunds", "The refund window is 30 days.", revision="r1")
        _apply(store, SCOPE_A, upserts=(shared,))
        _apply(store, SCOPE_B, upserts=(shared,))
        store.set_groups(SCOPE_A, "alice", {"support"})
        store.set_groups(SCOPE_B, "alice", {"support"})
        brain_a = CompanyBrain(store, SCOPE_A)
        brain_b = CompanyBrain(store, SCOPE_B)
        assert brain_a.answer(QUESTION, user_id="alice")["disposition"] == "grounded"

        key = _cache_key(QUESTION, "alice")
        from_a = _real_cached_payload(store, SCOPE_A, key)
        poisoned = _mutate(from_a, answer="CROSS-SCOPE-POISON")
        # A forger recomputes the unkeyed checksum but cannot forge the scope
        # binding; the request-identity check must still reject the record.
        _store_payload(store, SCOPE_B, key, poisoned, reseal=True)

        result = brain_b.answer(QUESTION, user_id="alice")
        _assert_safe_answer(result, forbidden=("CROSS-SCOPE-POISON",))
        assert result["cache_hit"] is False
        assert "30 days" in result["answer"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("dependencies", ["not-a-mapping"]),
        ("dependencies", [42]),
        ("evidence", ["not-a-mapping"]),
        ("evidence", [17]),
    ],
)
def test_malformed_record_entries_are_a_cache_miss(
    cached_brain: tuple[SQLiteBrainStore, CompanyBrain, str],
    field: str,
    value: object,
) -> None:
    store, brain, key = cached_brain
    base = _real_cached_payload(store, SCOPE_A, key)
    _store_payload(store, SCOPE_A, key, _mutate(base, **{field: value}), reseal=True)
    result = brain.answer(QUESTION, user_id="alice")
    _assert_safe_answer(result)
    assert result["cache_hit"] is False
    assert "30 days" in result["answer"]


def test_grounded_record_without_evidence_is_not_served(
    cached_brain: tuple[SQLiteBrainStore, CompanyBrain, str],
) -> None:
    store, brain, key = cached_brain
    base = _real_cached_payload(store, SCOPE_A, key)
    poisoned = _mutate(
        base,
        disposition="grounded",
        evidence=[],
        dependencies=[],
        answer="GROUNDED-WITHOUT-EVIDENCE",
    )
    _store_payload(store, SCOPE_A, key, poisoned, reseal=True)
    result = brain.answer(QUESTION, user_id="alice")
    _assert_safe_answer(result, forbidden=("GROUNDED-WITHOUT-EVIDENCE",))
    assert result["cache_hit"] is False
    assert "30 days" in result["answer"]


def test_invalid_cached_disposition_is_not_served(
    cached_brain: tuple[SQLiteBrainStore, CompanyBrain, str],
) -> None:
    store, brain, key = cached_brain
    base = _real_cached_payload(store, SCOPE_A, key)
    _store_payload(
        store,
        SCOPE_A,
        key,
        _mutate(base, disposition="totally-bogus"),
        reseal=True,
    )
    result = brain.answer(QUESTION, user_id="alice")
    _assert_safe_answer(result)
    assert result["cache_hit"] is False
    assert result["disposition"] == "grounded"


def test_wrong_evidence_revision_is_not_served(
    cached_brain: tuple[SQLiteBrainStore, CompanyBrain, str],
) -> None:
    store, brain, key = cached_brain
    base = _real_cached_payload(store, SCOPE_A, key)
    poisoned = _mutate(base)
    for row in poisoned["evidence"]:
        row["revision"] = "r999"
    _store_payload(store, SCOPE_A, key, poisoned, reseal=True)
    result = brain.answer(QUESTION, user_id="alice")
    _assert_safe_answer(result)
    assert result["cache_hit"] is False
    assert all(row.get("revision") != "r999" for row in result["evidence"])


def test_accidentally_corrupted_answer_field_is_not_served(
    cached_brain: tuple[SQLiteBrainStore, CompanyBrain, str],
) -> None:
    """Accidental corruption of the answer field must fail the record checksum.

    This is the *accidental* corruption model.  The engine's unkeyed checksum is
    documentation-stated as corruption detection, not authentication; a writer
    that deliberately re-seals a semantically poisoned answer is outside the
    trust model and is reported as a residual risk rather than asserted here.
    """

    store, brain, key = cached_brain
    base = _real_cached_payload(store, SCOPE_A, key)
    secret = "The Nimbus launch code is hunter2."
    poisoned = _mutate(base, answer=secret)
    _store_payload(store, SCOPE_A, key, poisoned)
    result = brain.answer(QUESTION, user_id="alice")
    _assert_safe_answer(result, forbidden=(secret, "hunter2"))
    assert result["cache_hit"] is False
    assert "30 days" in result["answer"]


@pytest.mark.parametrize("view_cache_bytes", [None, 1])
def test_view_eviction_never_serves_stale_content(
    tmp_path: Path, view_cache_bytes: int | None
) -> None:
    """A constant-eviction cache must still re-read on every durable change."""

    path = tmp_path / f"evict-{view_cache_bytes}.sqlite3"
    writer = SQLiteBrainStore(path)
    reader = SQLiteBrainStore(path)
    oracle = SQLiteBrainStore(path)
    try:
        policy = _document("refunds", "The refund window is 30 days.", revision="r1")
        _apply(writer, SCOPE_A, upserts=(policy,))
        writer.set_groups(SCOPE_A, "alice", {"support"})
        brain = CompanyBrain(
            reader,
            SCOPE_A,
            view_cache_size=8,
            view_cache_bytes=view_cache_bytes,
        )

        assert "30 days" in brain.answer(QUESTION, user_id="alice")["answer"]
        _check_pair(oracle, brain, SCOPE_A, "alice")

        edited = replace(
            policy, body="The refund window is 45 days.", content_digest=""
        )
        _apply(writer, SCOPE_A, upserts=(edited,))
        answer = brain.answer(QUESTION, user_id="alice")
        assert "45 days" in answer["answer"]
        assert "30 days" not in answer["answer"]
        _check_pair(oracle, brain, SCOPE_A, "alice")

        moved = replace(edited, content_digest="", acl=_acl(groups=("finance",)))
        _apply(writer, SCOPE_A, upserts=(moved,))
        assert "45 days" not in brain.answer(QUESTION, user_id="alice")["answer"]
        _check_pair(oracle, brain, SCOPE_A, "alice")
        _check_pair(oracle, brain, SCOPE_A, "bob")

        writer.set_groups(SCOPE_A, "bob", {"finance"})
        assert "45 days" in brain.answer(QUESTION, user_id="bob")["answer"]
        _check_pair(oracle, brain, SCOPE_A, "bob")
        assert brain.cache_stats().max_bytes == view_cache_bytes
    finally:
        oracle.close()
        reader.close()
        writer.close()


def test_valid_cached_record_survives_restart(
    tmp_path: Path,
) -> None:
    """Positive control: an untampered record is reused after a reopen."""

    path = tmp_path / "valid.sqlite3"
    with SQLiteBrainStore(path) as store:
        policy = _document("refunds", "The refund window is 30 days.", revision="r1")
        _apply(store, SCOPE_A, upserts=(policy,))
        store.set_groups(SCOPE_A, "alice", {"support"})
        first = CompanyBrain(store, SCOPE_A).answer(QUESTION, user_id="alice")
        assert first["disposition"] == "grounded"
    with SQLiteBrainStore(path) as reopened:
        restarted = CompanyBrain(reopened, SCOPE_A).answer(QUESTION, user_id="alice")
        assert restarted["cache_hit"] is True
        assert restarted["answer"] == first["answer"]
