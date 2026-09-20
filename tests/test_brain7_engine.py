"""Wave-7 engine regression: an opaque access token must not defeat invalidation.

The durable engine memoizes a fully authorized view under the store's access
token, then revalidates cached prose against the digest of that live view.  The
documented fast-path token exposes ``doc_epoch`` and ``membership_epoch``, but
the optional token API accepts any host token.  The engine used to key the view
cache on ``int(getattr(token, "doc_epoch", 0))`` /
``int(getattr(token, "membership_epoch", 0))``.  A store whose token is a
monotonic integer, a string, or a tuple therefore collapsed *every* token onto
``(0, 0)``: after a durable edit the engine reused the stale memoized view,
matched its stale authorized digest, and replayed the pre-edit answer from the
persisted cache with ``cache_hit=True``.

These tests pin the minimal fix in ``engine.py``:

* the view-cache key binds to the token's value when the token is not an epoch
  pair, so a value change rebuilds the view and invalidates the answer; and
* a ``None`` or unhashable token retains no view (degrading to the legacy
  uncached read) instead of colliding, while the durable answer cache still
  revalidates against the fresh live view.

The epoch-token path is unchanged and remains covered by the wave-3/4/5/6
suites; the positive control here guards the key change for the real store.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from examples.company_brains.durable.engine import CompanyBrain
from examples.company_brains.durable.store import AccessToken, SQLiteBrainStore
from mari_kit import (
    DocumentACL,
    KnowledgeDocument,
    PollPage,
    Principal,
    ScopeRef,
    SyncMode,
)
from mari_kit.sync import plan_sync

SOURCE = "wave7:handbook"
SCOPE = ScopeRef(tenant="wave7", space="brain")
QUESTION = "What is the refund window?"
OLD_BODY = "The refund window is 30 days."
NEW_BODY = "The refund window is 99 days."


def _document(body: str, revision: str = "v1") -> KnowledgeDocument:
    return KnowledgeDocument(
        source_id=SOURCE,
        external_id="refunds",
        title="Refund policy",
        body=body,
        revision=revision,
        acl=DocumentACL(
            visibility="restricted",
            principals=(Principal(kind="team", identifier="support"),),
        ),
    )


def _apply(store: SQLiteBrainStore, document: KnowledgeDocument) -> None:
    plan = plan_sync(
        store.state(SCOPE, SOURCE),
        PollPage(upserts=(document,), snapshot_complete=True),
        source_id=SOURCE,
        mode=SyncMode.INCREMENTAL,
    )
    store.apply_plan(SCOPE, plan)


class OpaqueTokenStore(SQLiteBrainStore):
    """Adapt actual SQLite epochs without losing membership or snapshot updates."""

    token_kind = "int"

    def _convert(self, token: AccessToken):
        pair = (token.doc_epoch, token.membership_epoch)
        if self.token_kind == "tuple":
            return pair
        if self.token_kind == "str":
            return f"{pair[0]}:{pair[1]}"
        if self.token_kind == "list":
            return list(pair)
        # Cantor pairing preserves both nonnegative integer counters.
        total = sum(pair)
        return total * (total + 1) // 2 + pair[1]

    def access_token(self, scope: ScopeRef, user_id: str):
        return self._convert(super().access_token(scope, user_id))

    def access_token_snapshot(self, scope: ScopeRef, user_id: str):
        token, documents, groups = super().access_token_snapshot(scope, user_id)
        return self._convert(token), documents, groups


def _warm(store: SQLiteBrainStore) -> CompanyBrain:
    _apply(store, _document(OLD_BODY))
    store.set_groups(SCOPE, "alice", {"support"})
    brain = CompanyBrain(store, SCOPE)
    warm = brain.answer(QUESTION, user_id="alice")
    assert warm["disposition"] == "grounded"
    assert OLD_BODY in str(warm["answer"])
    assert brain.answer(QUESTION, user_id="alice")["cache_hit"] is True
    return brain


def _edit(store: SQLiteBrainStore, brain: CompanyBrain) -> dict:
    _apply(store, _document(NEW_BODY, revision="v2"))
    return brain.answer(QUESTION, user_id="alice")


@pytest.mark.parametrize("token_kind", ["int", "str", "tuple"])
def test_opaque_token_change_invalidates_the_memoized_view(
    tmp_path: Path, token_kind: str
) -> None:
    """Regression: a value-bearing opaque token must not replay pre-edit prose."""

    with OpaqueTokenStore(str(tmp_path / "opaque.sqlite3")) as store:
        store.token_kind = token_kind
        brain = _warm(store)
        after = _edit(store, brain)
        assert after["cache_hit"] is False
        assert after["disposition"] == "grounded"
        assert NEW_BODY in str(after["answer"])
        assert OLD_BODY not in str(after["answer"])
        assert brain.answer(QUESTION, user_id="alice")["cache_hit"] is True
        store.set_groups(SCOPE, "alice", ())
        revoked = brain.answer(QUESTION, user_id="alice")
        assert revoked["cache_hit"] is False
        assert revoked["disposition"] == "insufficient_evidence"
        assert revoked["evidence"] == []
        assert brain.search("refund", user_id="alice") == ()


def test_unhashable_token_is_not_retained_but_stays_correct(tmp_path: Path) -> None:
    """An unbindable token degrades to the uncached read, never to a collision."""

    with OpaqueTokenStore(str(tmp_path / "unhashable.sqlite3")) as store:
        store.token_kind = "list"
        brain = _warm(store)
        after = _edit(store, brain)
        assert after["disposition"] == "grounded"
        assert NEW_BODY in str(after["answer"])
        assert OLD_BODY not in str(after["answer"])
        assert brain.cache_stats().views == 0


def test_epoch_token_store_still_retains_and_invalidates(tmp_path: Path) -> None:
    """Positive control: the documented epoch token keeps the fast path."""

    with SQLiteBrainStore(str(tmp_path / "epoch.sqlite3")) as store:
        brain = _warm(store)
        assert brain.cache_stats().views == 1
        refreshed = _edit(store, brain)
        assert refreshed["cache_hit"] is False
        assert NEW_BODY in str(refreshed["answer"])
        assert brain.cache_stats().views == 1


@pytest.mark.parametrize(
    "invalid_token",
    [
        None,
        SimpleNamespace(doc_epoch=1),
        SimpleNamespace(doc_epoch=1.5, membership_epoch=2),
        SimpleNamespace(doc_epoch=-1, membership_epoch=2),
    ],
)
def test_invalid_epoch_tokens_use_fresh_snapshots(tmp_path, invalid_token):
    class InvalidTokenStore(OpaqueTokenStore):
        def _convert(self, token):
            return invalid_token

    with InvalidTokenStore(tmp_path / "invalid.sqlite3") as store:
        brain = _warm(store)
        after = _edit(store, brain)
        assert after["cache_hit"] is False
        assert NEW_BODY in str(after["answer"])
        assert brain.cache_stats().views == 0
        store.set_groups(SCOPE, "alice", ())
        assert brain.answer(QUESTION, user_id="alice")["evidence"] == []
