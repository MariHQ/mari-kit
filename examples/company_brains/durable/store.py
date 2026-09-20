"""Durable SQLite backing store for the company-brain reference application.

Mari Kit stays backend-agnostic: it supplies immutable document values, the
side-effect-free sync planner, and the optimistic generation contract.  This
host-owned module decides how bytes survive.  Every synchronization plan is
applied in a single SQLite transaction that advances the live documents, the
durable lexical projection, and the source sync state together; an interrupted
plan leaves no partial observation behind.

The store is scope-isolated (tenant/space), source-bound, and opens one
short-lived SQLite connection per instance so independent processes observe
freshly committed rows.  Access control state (groups, ACL principals) and the
answer cache are durable too, and ``access_snapshot`` reads documents and
memberships from one consistent read transaction.

In addition to full snapshots, the store maintains two cheap, monotonically
increasing epoch counters per scope: a document epoch advanced by every plan
that changes visible documents, and a per-user membership epoch advanced only
when that user's groups actually change.  ``access_token`` reads these counters
in one statement, while ``access_token_snapshot`` reads a token together with
the documents and memberships inside a single read transaction.  Callers can
therefore memoize full snapshots under a cheap token without ever tagging a
stale snapshot with a newer token.
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from mari_kit import (
    DocumentACL,
    KnowledgeDocument,
    Principal,
    ScopeRef,
    SyncMode,
    Tombstone,
)
from mari_kit.json import to_json_value
from mari_kit.sync import ManifestEntry, SyncPlan, SyncState, document_fingerprint

_BUSY_TIMEOUT_MS = 5000
_DB_FILENAME = "brain.sqlite3"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    tenant TEXT NOT NULL,
    space TEXT NOT NULL,
    document_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    external_id TEXT NOT NULL,
    revision TEXT NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY (tenant, space, document_id)
);

CREATE TABLE IF NOT EXISTS document_history (
    tenant TEXT NOT NULL,
    space TEXT NOT NULL,
    document_id TEXT NOT NULL,
    revision TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY (tenant, space, document_id, revision, fingerprint)
);

CREATE TABLE IF NOT EXISTS projections (
    tenant TEXT NOT NULL,
    space TEXT NOT NULL,
    document_id TEXT NOT NULL,
    body TEXT NOT NULL,
    PRIMARY KEY (tenant, space, document_id)
);

CREATE TABLE IF NOT EXISTS sync_states (
    tenant TEXT NOT NULL,
    space TEXT NOT NULL,
    source_id TEXT NOT NULL,
    generation INTEGER NOT NULL,
    state TEXT NOT NULL,
    PRIMARY KEY (tenant, space, source_id)
);

CREATE TABLE IF NOT EXISTS groups (
    tenant TEXT NOT NULL,
    space TEXT NOT NULL,
    user_id TEXT NOT NULL,
    group_id TEXT NOT NULL,
    PRIMARY KEY (tenant, space, user_id, group_id)
);

CREATE TABLE IF NOT EXISTS cache (
    tenant TEXT NOT NULL,
    space TEXT NOT NULL,
    cache_key TEXT NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY (tenant, space, cache_key)
);

CREATE TABLE IF NOT EXISTS scope_epochs (
    tenant TEXT NOT NULL,
    space TEXT NOT NULL,
    doc_epoch INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (tenant, space)
);

CREATE TABLE IF NOT EXISTS membership_epochs (
    tenant TEXT NOT NULL,
    space TEXT NOT NULL,
    user_id TEXT NOT NULL,
    membership_epoch INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (tenant, space, user_id)
);
"""


@dataclass(frozen=True, slots=True)
class AccessToken:
    """A cheap, monotonic fingerprint of the live access-relevant state.

    A token pairs the scope's document epoch with one user's membership epoch.
    Within the same store, scope, and user, equal tokens imply equal live
    documents and equal group memberships, so an authorized snapshot memoized under a token stays valid
    until a durable change advances one of the counters.
    """

    doc_epoch: int = 0
    membership_epoch: int = 0


def _resolve_path(path: str | os.PathLike[str]) -> str:
    """Accept a database file, a directory to hold one, or ``:memory:``."""

    candidate = os.fspath(path)
    if candidate == ":memory:" or candidate.startswith("file:"):
        return candidate
    if os.path.isdir(candidate):
        candidate = os.path.join(candidate, _DB_FILENAME)
    parent = os.path.dirname(os.path.abspath(candidate))
    os.makedirs(parent, exist_ok=True)
    return candidate


def _encode(value: Any) -> str:
    """Encode any Mari JSON value deterministically and losslessly."""

    return json.dumps(
        to_json_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _decode_document(text: str) -> KnowledgeDocument:
    data = json.loads(text)
    acl_data = data.get("acl") or {}
    principals = tuple(
        Principal(kind=item["kind"], identifier=item["identifier"])
        for item in (acl_data.get("principals") or ())
    )
    return KnowledgeDocument(
        source_id=data["source_id"],
        external_id=data["external_id"],
        title=data["title"],
        body=data["body"],
        revision=data["revision"],
        provider_revision=data.get("provider_revision", ""),
        updated_at=data.get("updated_at", ""),
        source_url=data.get("source_url", ""),
        acl=DocumentACL(
            visibility=acl_data.get("visibility", "connector_scope"),
            principals=principals,
        ),
        metadata=data.get("metadata") or {},
    )


def _decode_state(text: str) -> SyncState:
    data = json.loads(text)
    manifest = {
        key: ManifestEntry(
            fingerprint=value["fingerprint"],
            revision=value["revision"],
            source_id=value["source_id"],
            external_id=value["external_id"],
        )
        for key, value in (data.get("manifest") or {}).items()
    }
    active_mode = data.get("active_mode")
    return SyncState(
        source_id=data.get("source_id", ""),
        configuration_fingerprint=data.get("configuration_fingerprint", ""),
        cursor=data.get("cursor"),
        checkpoint=data.get("checkpoint"),
        manifest=manifest,
        full_seen=frozenset(data.get("full_seen") or ()),
        active_mode=SyncMode(active_mode) if active_mode else None,
        generation=int(data.get("generation", 0)),
    )


def _load_documents(
    connection: sqlite3.Connection, scope: ScopeRef
) -> tuple[KnowledgeDocument, ...]:
    rows = connection.execute(
        "SELECT payload FROM documents WHERE tenant = ? AND space = ? "
        "ORDER BY document_id",
        scope.key,
    ).fetchall()
    return tuple(_decode_document(row[0]) for row in rows)


def _load_groups(
    connection: sqlite3.Connection, scope: ScopeRef, user_id: str
) -> frozenset[str]:
    rows = connection.execute(
        "SELECT group_id FROM groups WHERE tenant = ? AND space = ? AND user_id = ? "
        "ORDER BY group_id",
        (*scope.key, user_id),
    ).fetchall()
    return frozenset(row[0] for row in rows)


def _read_token(
    connection: sqlite3.Connection, scope: ScopeRef, user_id: str
) -> AccessToken:
    """Read both epochs in one statement without touching document rows."""

    row = connection.execute(
        "SELECT "
        "(SELECT doc_epoch FROM scope_epochs "
        " WHERE tenant = ? AND space = ?), "
        "(SELECT membership_epoch FROM membership_epochs "
        " WHERE tenant = ? AND space = ? AND user_id = ?)",
        (*scope.key, *scope.key, user_id),
    ).fetchone()
    doc_epoch = int(row[0]) if row and row[0] is not None else 0
    membership_epoch = int(row[1]) if row and row[1] is not None else 0
    return AccessToken(doc_epoch=doc_epoch, membership_epoch=membership_epoch)


def _bump_scope_epoch(connection: sqlite3.Connection, scope: ScopeRef) -> None:
    connection.execute(
        "INSERT INTO scope_epochs (tenant, space, doc_epoch) VALUES (?, ?, 1) "
        "ON CONFLICT (tenant, space) DO UPDATE SET "
        "doc_epoch = scope_epochs.doc_epoch + 1",
        scope.key,
    )


def _bump_membership_epoch(
    connection: sqlite3.Connection, scope: ScopeRef, user_id: str
) -> None:
    connection.execute(
        "INSERT INTO membership_epochs "
        "(tenant, space, user_id, membership_epoch) VALUES (?, ?, ?, 1) "
        "ON CONFLICT (tenant, space, user_id) DO UPDATE SET "
        "membership_epoch = membership_epochs.membership_epoch + 1",
        (*scope.key, user_id),
    )


class SQLiteBrainStore:
    """Durable, scope-isolated store with one transaction per sync plan."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = _resolve_path(path)
        self._connection = sqlite3.connect(
            self.path,
            timeout=_BUSY_TIMEOUT_MS / 1000,
            isolation_level=None,
        )
        self._connection.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
        self._connection.execute("PRAGMA synchronous = FULL")
        if self.path != ":memory:":
            self._connection.execute("PRAGMA journal_mode = WAL")
        self._connection.executescript(_SCHEMA)

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None  # type: ignore[assignment]

    def __enter__(self) -> SQLiteBrainStore:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def state(self, scope: ScopeRef, source_id: str) -> SyncState:
        row = self._connection.execute(
            "SELECT state FROM sync_states "
            "WHERE tenant = ? AND space = ? AND source_id = ?",
            (*scope.key, source_id),
        ).fetchone()
        return _decode_state(row[0]) if row else SyncState()

    def documents(self, scope: ScopeRef) -> tuple[KnowledgeDocument, ...]:
        return _load_documents(self._connection, scope)

    def get_document(
        self, scope: ScopeRef, document_id: str
    ) -> KnowledgeDocument | None:
        row = self._connection.execute(
            "SELECT payload FROM documents "
            "WHERE tenant = ? AND space = ? AND document_id = ?",
            (*scope.key, document_id),
        ).fetchone()
        return _decode_document(row[0]) if row else None

    def projection(self, scope: ScopeRef) -> dict[str, str]:
        rows = self._connection.execute(
            "SELECT document_id, body FROM projections "
            "WHERE tenant = ? AND space = ? ORDER BY document_id",
            scope.key,
        ).fetchall()
        return {row[0]: row[1] for row in rows}

    def set_groups(self, scope: ScopeRef, user_id: str, groups: Iterable[str]) -> None:
        normalized = sorted(
            {
                group.strip()
                for group in groups
                if isinstance(group, str) and group.strip()
            }
        )
        connection = self._connection
        connection.execute("BEGIN IMMEDIATE")
        try:
            if _load_groups(connection, scope, user_id) == frozenset(normalized):
                connection.execute("COMMIT")
                return
            connection.execute(
                "DELETE FROM groups WHERE tenant = ? AND space = ? AND user_id = ?",
                (*scope.key, user_id),
            )
            connection.executemany(
                "INSERT INTO groups (tenant, space, user_id, group_id) "
                "VALUES (?, ?, ?, ?)",
                [(*scope.key, user_id, group) for group in normalized],
            )
            _bump_membership_epoch(connection, scope, user_id)
            connection.execute("COMMIT")
        except BaseException:
            connection.execute("ROLLBACK")
            raise

    def groups(self, scope: ScopeRef, user_id: str) -> frozenset[str]:
        return _load_groups(self._connection, scope, user_id)

    def access_snapshot(
        self, scope: ScopeRef, user_id: str
    ) -> tuple[tuple[KnowledgeDocument, ...], frozenset[str]]:
        connection = self._connection
        connection.execute("BEGIN")
        try:
            documents = _load_documents(connection, scope)
            groups = _load_groups(connection, scope, user_id)
            connection.execute("COMMIT")
        except BaseException:
            connection.execute("ROLLBACK")
            raise
        return documents, groups

    def access_token(self, scope: ScopeRef, user_id: str) -> AccessToken:
        """Return the current cheap access token without reading documents."""

        return _read_token(self._connection, scope, user_id)

    def access_token_snapshot(
        self, scope: ScopeRef, user_id: str
    ) -> tuple[AccessToken, tuple[KnowledgeDocument, ...], frozenset[str]]:
        """Read a token and the matching documents/memberships atomically.

        The token is read from the same read transaction as the rows, so a
        caller caching the snapshot under the token can never associate a
        newer token with an older snapshot (or the reverse).
        """

        connection = self._connection
        connection.execute("BEGIN")
        try:
            token = _read_token(connection, scope, user_id)
            documents = _load_documents(connection, scope)
            groups = _load_groups(connection, scope, user_id)
            connection.execute("COMMIT")
        except BaseException:
            connection.execute("ROLLBACK")
            raise
        return token, documents, groups

    def save_cache(self, scope: ScopeRef, key: str, payload: dict) -> None:
        self._connection.execute(
            "INSERT INTO cache (tenant, space, cache_key, payload) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT (tenant, space, cache_key) "
            "DO UPDATE SET payload = excluded.payload",
            (*scope.key, key, _encode(payload)),
        )

    def load_cache(self, scope: ScopeRef, key: str) -> dict | None:
        row = self._connection.execute(
            "SELECT payload FROM cache "
            "WHERE tenant = ? AND space = ? AND cache_key = ?",
            (*scope.key, key),
        ).fetchone()
        if row is None:
            return None
        try:
            payload = json.loads(row[0])
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    def apply_plan(
        self,
        scope: ScopeRef,
        plan: SyncPlan,
        *,
        failpoint: Callable[[str], None] | None = None,
    ) -> None:
        """Atomically advance documents, projection, and sync state."""

        self._reject_foreign_sources(plan)
        connection = self._connection
        connection.execute("BEGIN IMMEDIATE")
        try:
            current = self._current_generation(connection, scope, plan.state.source_id)
            if current != plan.expected_generation:
                raise ValueError(
                    f"sync generation mismatch: expected "
                    f"{plan.expected_generation}, found {current}"
                )
            self._write_documents(connection, scope, plan)
            if plan.upserts or plan.deletes:
                _bump_scope_epoch(connection, scope)
            self._call(failpoint, "after_documents")
            self._write_projection(connection, scope, plan)
            self._call(failpoint, "after_projection")
            self._write_state(connection, scope, plan.state)
            self._call(failpoint, "before_commit")
            connection.execute("COMMIT")
        except BaseException:
            try:
                connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        self._call(failpoint, "after_commit")

    @staticmethod
    def _reject_foreign_sources(plan: SyncPlan) -> None:
        source_id = plan.state.source_id
        if not source_id.strip():
            raise ValueError("plan source_id is required")
        changes: tuple[KnowledgeDocument | Tombstone, ...] = (
            *plan.upserts,
            *plan.deletes,
        )
        foreign = sorted(
            {item.source_id for item in changes if item.source_id != source_id}
        )
        if foreign:
            raise ValueError(f"plan contains foreign sources: {foreign!r}")
        if plan.state.generation != plan.expected_generation + 1:
            raise ValueError("plan state generation must advance by exactly one")

    @staticmethod
    def _current_generation(
        connection: sqlite3.Connection, scope: ScopeRef, source_id: str
    ) -> int:
        row = connection.execute(
            "SELECT generation FROM sync_states "
            "WHERE tenant = ? AND space = ? AND source_id = ?",
            (*scope.key, source_id),
        ).fetchone()
        return int(row[0]) if row else 0

    @staticmethod
    def _write_documents(
        connection: sqlite3.Connection, scope: ScopeRef, plan: SyncPlan
    ) -> None:
        for tombstone in plan.deletes:
            connection.execute(
                "DELETE FROM documents "
                "WHERE tenant = ? AND space = ? AND document_id = ?",
                (*scope.key, tombstone.document_id),
            )
        for document in plan.upserts:
            payload = _encode(document)
            connection.execute(
                "INSERT INTO documents "
                "(tenant, space, document_id, source_id, external_id, revision, "
                "payload) VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (tenant, space, document_id) DO UPDATE SET "
                "source_id = excluded.source_id, "
                "external_id = excluded.external_id, "
                "revision = excluded.revision, payload = excluded.payload",
                (
                    *scope.key,
                    document.document_id,
                    document.source_id,
                    document.external_id,
                    document.revision,
                    payload,
                ),
            )
            connection.execute(
                "INSERT OR IGNORE INTO document_history "
                "(tenant, space, document_id, revision, fingerprint, payload) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    *scope.key,
                    document.document_id,
                    document.revision,
                    document_fingerprint(document),
                    payload,
                ),
            )

    @staticmethod
    def _write_projection(
        connection: sqlite3.Connection, scope: ScopeRef, plan: SyncPlan
    ) -> None:
        for tombstone in plan.deletes:
            connection.execute(
                "DELETE FROM projections "
                "WHERE tenant = ? AND space = ? AND document_id = ?",
                (*scope.key, tombstone.document_id),
            )
        for document in plan.upserts:
            connection.execute(
                "INSERT INTO projections "
                "(tenant, space, document_id, body) VALUES (?, ?, ?, ?) "
                "ON CONFLICT (tenant, space, document_id) DO UPDATE SET "
                "body = excluded.body",
                (*scope.key, document.document_id, document.body),
            )

    @staticmethod
    def _write_state(
        connection: sqlite3.Connection, scope: ScopeRef, state: SyncState
    ) -> None:
        connection.execute(
            "INSERT INTO sync_states "
            "(tenant, space, source_id, generation, state) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT (tenant, space, source_id) DO UPDATE SET "
            "generation = excluded.generation, state = excluded.state",
            (*scope.key, state.source_id, state.generation, _encode(state)),
        )

    @staticmethod
    def _call(failpoint: Callable[[str], None] | None, stage: str) -> None:
        if failpoint is not None:
            failpoint(stage)
