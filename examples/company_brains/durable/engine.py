"""Durable, permission-aware company brain built on the host's SQLite store.

This module owns authorization and the answer lifecycle for the durable
reference application. The store is the sole source of live documents, group
memberships, and cached answers; the brain never trusts constructor-time state.
Every request checks live access state and applies the host policy explicitly:

* ``public`` and ``connector_scope`` documents are visible to the tenant;
* ``restricted`` documents require a ``team`` principal matching one of the
  caller's current groups, or a ``user`` principal matching the caller.

Generated output is validated with :func:`mari_kit.knowledge.parse_answer`
against only the authorized documents, so a model callback cannot cite a hidden
source. Cached and freshly generated answers are revalidated against the current
authorized view immediately before they are served, so an edit, deletion,
same-revision ACL change, title/metadata change, or group membership change can
never surface stale prose.

Persisted records carry a fixed-width SHA-256 *digest* of the authorized set
(schema ``company-brain-answer-v3``) instead of the full per-document fingerprint
list, so a stored record's size does not grow with the number of unrelated
authorized documents.  The digest is computed once when a view is built; a view
also precomputes its ``document_id -> document`` map once so a cache hit never
rebuilds it.  Both additions are charged through :func:`_retained_size`, whose
identity dedup means the shared document objects are not double-counted.

Unchanged requests are cheap.  The store exposes a monotonically increasing
access token (a scope document epoch plus the caller's membership epoch).  Each
``CompanyBrain`` memoizes the fully authorized snapshot and its lazily built
BM25 index under that token in a bounded cache.  A request whose cheap token is
already cached answers from memory without rereading document rows or rebuilding
the index, while a durable edit, delete, ACL change, or group change advances
the token and forces a fresh, transactionally consistent snapshot.  Stores that
only implement the legacy ``access_snapshot`` API still work, uncached.
"""

from __future__ import annotations

import hashlib
import re
from collections import OrderedDict
from collections.abc import Callable, Collection, Iterable, Mapping
from dataclasses import dataclass, fields, is_dataclass
from sys import getsizeof
from typing import Protocol, cast

from mari_kit import DocumentACL, Evidence, KnowledgeDocument, ScopeRef
from mari_kit.errors import MalformedModelOutput
from mari_kit.json import canonical_json_bytes
from mari_kit.knowledge import AnswerDisposition, GroundedAnswer, parse_answer
from mari_kit.retrieval import BM25Index, RevisionBM25Index
from mari_kit.sync import document_fingerprint

from .cache_records import cache_record_matches_request, seal_cache_record

CACHE_SCHEMA = "company-brain-answer-v3"
ABSTENTION_TEXT = "No authorized evidence is available for this question."
EXTRACTIVE_LABEL = "Deterministic extractive answer: "
_MAX_ATTEMPTS = 3
_DEFAULT_VIEW_CACHE_SIZE = 8

# A view-cache key binds one caller's scope and user to one live access token.
# The token component is the documented epoch pair when the host exposes it, or
# the opaque token value itself otherwise. ``None`` means the token cannot be
# bound safely, so the view is not retained.
_ViewKey = tuple[tuple[str, str], str, object]

_TENANT_VISIBLE = frozenset({"public", "connector_scope"})
_SENTENCE = re.compile(r"[^.!?\n]+[.!?]?")
_WORD = re.compile(r"\w+")

Generate = Callable[[str, tuple[KnowledgeDocument, ...]], object]


class BrainStore(Protocol):
    """The subset of the durable store that the engine depends on.

    ``access_token``/``access_token_snapshot`` are optional fast-path
    extensions; the engine falls back to ``access_snapshot`` alone when a store
    does not provide them. Tokens must have stable equality: an equal token
    must imply equal documents and memberships for the same scope and user.
    The snapshot extension must return its token and rows from one consistent
    read. Tokens may expose two nonnegative integer epochs or be immutable,
    hashable opaque values. Unsupported tokens disable view retention.
    """

    def access_snapshot(
        self, scope: ScopeRef, user_id: str
    ) -> tuple[tuple[KnowledgeDocument, ...], frozenset[str]]: ...

    def load_cache(self, scope: ScopeRef, key: str) -> dict | None: ...

    def save_cache(self, scope: ScopeRef, key: str, payload: dict) -> None: ...


def user_authorized(
    document: KnowledgeDocument,
    *,
    user_id: str,
    groups: Collection[str],
) -> bool:
    """Apply the explicit host policy to one live document observation."""

    acl: DocumentACL = document.acl
    if acl.visibility in _TENANT_VISIBLE:
        return True
    for principal in acl.principals:
        if principal.kind == "user" and principal.identifier == user_id:
            return True
        if principal.kind == "team" and principal.identifier in groups:
            return True
    return False


def authorized_documents(
    documents: Iterable[KnowledgeDocument],
    *,
    user_id: str,
    groups: Collection[str],
) -> tuple[KnowledgeDocument, ...]:
    return tuple(
        document
        for document in documents
        if user_authorized(document, user_id=user_id, groups=groups)
    )


def authorized_fingerprint(
    documents: Iterable[KnowledgeDocument],
) -> tuple[str, ...]:
    """Fingerprint the exact authorized set, including ACL and metadata.

    Two snapshots with the same fingerprint have identical visible content,
    revisions, visibility, principals, and metadata, so a cached answer
    validated against one remains valid for the other.
    """

    return tuple(
        hashlib.sha256(
            canonical_json_bytes(
                {
                    "document_id": document.document_id,
                    "fingerprint": document_fingerprint(document),
                }
            )
        ).hexdigest()
        for document in sorted(documents, key=lambda item: item.document_id)
    )


def fingerprint_digest(fingerprint: Iterable[str]) -> str:
    """Collapse an ordered fingerprint sequence into one fixed-width SHA-256.

    The digest is a compact, deterministic summary of the exact authorized set:
    identical fingerprints yield identical digests and any difference in a
    document id, revision, visibility, principal, title, body, or metadata
    changes it.  It is the only authorized-set material persisted in a cache
    record, so record size is independent of the authorized corpus size.
    """

    return hashlib.sha256(canonical_json_bytes(list(fingerprint))).hexdigest()


def authorized_digest(documents: Iterable[KnowledgeDocument]) -> str:
    """Return the compact digest of the exact authorized set."""

    return fingerprint_digest(authorized_fingerprint(documents))


def _validate_budget(
    name: str, value: int | None, *, allow_none: bool = False
) -> int | None:
    """Reject boolean, non-integer, and negative cache budget values."""

    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer, not {type(value).__name__}")
    if value < 0:
        raise ValueError(f"{name} must not be negative")
    return int(value)


def _retained_size(*roots: object) -> int:
    """Estimate retained Python bytes, deduplicating objects within one view.

    Traverse only the known value/container/index types, never callback globals
    or the owning brain/store. Shared objects across separate views are counted
    separately. Allocator overhead and temporary build allocations are excluded.
    """
    pending = list(roots)
    seen: set[int] = set()
    total = 0
    while pending:
        value = pending.pop()
        identity = id(value)
        if identity in seen:
            continue
        seen.add(identity)
        total += getsizeof(value)
        if isinstance(value, Mapping):
            pending.extend(value.keys())
            pending.extend(value.values())
        elif isinstance(value, (tuple, list, set, frozenset)):
            pending.extend(value)
        elif is_dataclass(value) and not isinstance(value, type):
            pending.extend(getattr(value, field.name) for field in fields(value))
        elif isinstance(value, (BM25Index, RevisionBM25Index)):
            pending.append(vars(value))
    return total


@dataclass(frozen=True, slots=True)
class ViewCacheStats:
    """Read-only accounting for one brain's authorized-view cache.

    ``retained_estimated_bytes`` is the engine's explicit retained-size estimate
    summed over the currently cached views (see
    :func:`_retained_size`).  It is *not* an RSS reading and not a hard
    process-memory cap: interpreter interning, shared strings, and allocator
    overhead mean the process can use more or less than this number.  The byte
    budget uses the same estimate, so the two are internally consistent.
    """

    views: int
    retained_estimated_bytes: int
    evictions: int
    evicted_estimated_bytes: int
    max_views: int
    max_bytes: int | None


def _evidence_record(evidence: Evidence) -> dict[str, object]:
    return {
        "document_id": evidence.document_id,
        "revision": evidence.revision,
        "quote": evidence.quote,
        "section_id": evidence.section_id,
        "start": evidence.start,
        "end": evidence.end,
    }


class _AuthorizedView:
    """An authorized snapshot memoized under one live access token.

    The BM25 index is built lazily so answering with a host-supplied callback
    never pays for an index it will not use, while a second ``search`` or
    extractive ``answer`` for the same token reuses the first build.  Building
    the index grows the view's retained-size estimate, so the owner is notified
    once so it can re-enforce its byte budget.

    The view intentionally keeps only the document tuple, the ``ref ->
    document`` map, and a precomputed ``document_id -> document`` map.  The
    by-id map points at the very same pinned document objects, so a cache hit
    answers in O(1) per cited document instead of rebuilding an O(N) map on
    every request.  :func:`_retained_size` deduplicates by object identity, so
    the shared values are charged once and the existing byte bounds stay
    accurate.
    """

    __slots__ = (
        "token",
        "documents",
        "fingerprint",
        "digest",
        "refs",
        "_by_id",
        "_index",
        "_base_bytes",
        "_index_bytes",
        "_on_index_built",
    )

    def __init__(
        self,
        token: object | None,
        documents: tuple[KnowledgeDocument, ...],
        fingerprint: tuple[str, ...],
        digest: str,
        refs: Mapping[object, KnowledgeDocument],
        by_id: Mapping[str, KnowledgeDocument],
        *,
        on_index_built: Callable[[_AuthorizedView], None] | None = None,
    ) -> None:
        self.token = token
        self.documents = documents
        self.fingerprint = fingerprint
        self.digest = digest
        self.refs = refs
        self._by_id = by_id
        self._index: RevisionBM25Index | None = None
        self._index_bytes = 0
        self._on_index_built = on_index_built
        self._base_bytes = self._estimate_base_bytes()

    def _estimate_base_bytes(self) -> int:
        """Estimate the pinned bytes before the lazy index exists."""

        return getsizeof(self) + _retained_size(
            self.token,
            self.documents,
            self.fingerprint,
            self.digest,
            self.refs,
            self._by_id,
        )

    def _estimate_index_bytes(self) -> int:
        """Count index containers, tokens, and weights as well as source text."""
        combined = getsizeof(self) + _retained_size(
            self.token,
            self.documents,
            self.fingerprint,
            self.digest,
            self.refs,
            self._by_id,
            self._index,
        )
        return max(0, combined - self._base_bytes)

    def estimated_bytes(self) -> int:
        """Return the current retained-size estimate, including the index."""

        return self._base_bytes + self._index_bytes

    @property
    def index(self) -> RevisionBM25Index:
        if self._index is None:
            self._index = RevisionBM25Index(
                {
                    ref: f"{document.title} {document.body}"
                    for ref, document in self.refs.items()
                }
            )
            self._index_bytes = self._estimate_index_bytes()
            if self._on_index_built is not None:
                self._on_index_built(self)
        return self._index


class CompanyBrain:
    """Permission-aware answering over one durable, scoped store."""

    def __init__(
        self,
        store: BrainStore,
        scope: ScopeRef,
        *,
        view_cache_size: int = _DEFAULT_VIEW_CACHE_SIZE,
        view_cache_bytes: int | None = None,
    ) -> None:
        self._store = store
        self.scope = scope
        self._view_cache_size = cast(
            int, _validate_budget("view_cache_size", view_cache_size)
        )
        self._view_cache_bytes = _validate_budget(
            "view_cache_bytes", view_cache_bytes, allow_none=True
        )
        self._views: OrderedDict[_ViewKey, _AuthorizedView] = OrderedDict()
        self._view_evictions = 0
        self._evicted_estimated_bytes = 0

    def search(
        self, query: str, *, user_id: str, limit: int = 5
    ) -> tuple[KnowledgeDocument, ...]:
        """Return positive-scoring authorized documents in BM25 rank order."""

        if limit < 0:
            raise ValueError("limit must not be negative")
        if limit == 0:
            return ()
        view = self._view(user_id, indexed=True)
        if not view.documents:
            return ()
        refs = view.refs
        hits = view.index.search(query, limit=limit, allowed_refs=refs.keys())
        results: list[KnowledgeDocument] = []
        for hit in hits:
            if hit.score <= 0.0:
                break
            results.append(refs[hit.ref])
            if len(results) >= limit:
                break
        return tuple(results)

    def answer(
        self,
        question: str,
        *,
        user_id: str,
        generate: Generate | None = None,
    ) -> dict[str, object]:
        """Return a validated, freshly rechecked answer or a labeled abstention."""

        question = question.strip()
        if not question:
            raise ValueError("question is required")
        key = self._cache_key(question, user_id)
        cached = self._store.load_cache(self.scope, key)
        if isinstance(cached, dict):
            served = self._serve_cached(cached, question=question, user_id=user_id)
            if served is not None:
                return served
        payload, uncacheable = self._generate(
            question, user_id=user_id, generate=generate
        )
        if not uncacheable:
            payload["scope_key"] = list(self.scope.key)
            payload = seal_cache_record(payload)
            self._store.save_cache(self.scope, key, payload)
        return self._present(payload, cache_hit=False)

    def _view(self, user_id: str, *, indexed: bool = False) -> _AuthorizedView:
        """Return the live view; build requested indexes before new admission."""

        snapshot = getattr(self._store, "access_token_snapshot", None)
        reader = getattr(self._store, "access_token", None)
        if callable(snapshot) and callable(reader):
            token = reader(self.scope, user_id)
            cached = self._lookup_view(user_id, token)
            if cached is not None:
                return cached
            current_token, documents, groups = snapshot(self.scope, user_id)
            cached = self._lookup_view(user_id, current_token)
            if cached is not None:
                return cached
            view = self._build_view(current_token, documents, groups, user_id)
            # Search requires the index immediately. Account for its full size
            # before admission can evict an existing warm view. Callback-only
            # answers keep their indexes lazy.
            if indexed and view.documents:
                _ = view.index
            self._store_view(user_id, current_token, view)
            return view
        documents, groups = self._store.access_snapshot(self.scope, user_id)
        return self._build_view(None, documents, groups, user_id)

    def _build_view(
        self,
        token: object | None,
        documents: tuple[KnowledgeDocument, ...],
        groups: frozenset[str],
        user_id: str,
    ) -> _AuthorizedView:
        authorized = authorized_documents(documents, user_id=user_id, groups=groups)
        refs = {document.ref_in(self.scope): document for document in authorized}
        by_id = {document.document_id: document for document in authorized}
        fingerprint = authorized_fingerprint(authorized)
        return _AuthorizedView(
            token,
            authorized,
            fingerprint,
            fingerprint_digest(fingerprint),
            refs,
            by_id,
            on_index_built=self._after_index_built,
        )

    def _lookup_view(
        self, user_id: str, token: object | None
    ) -> _AuthorizedView | None:
        key = self._view_key(user_id, token)
        if key is None:
            return None
        view = self._views.get(key)
        if view is not None:
            self._views.move_to_end(key)
        return view

    def _store_view(
        self, user_id: str, token: object | None, view: _AuthorizedView
    ) -> None:
        key = self._view_key(user_id, token)
        if key is None:
            return
        self._views[key] = view
        self._views.move_to_end(key)
        # A token change means every older view for this scope/user is obsolete;
        # drop it now so per-user growth tracks live state, not edit history.
        # This holds even when the replacement view is itself too large to
        # cache: revocation must never leave the old view behind.
        self._evict_obsolete_views(user_id, key)
        self._enforce_view_limits(self._views.get(key))

    def _after_index_built(self, view: _AuthorizedView) -> None:
        """Re-enforce bounds now that a lazily built index grew a view."""

        self._enforce_view_limits(view)

    def _evict_obsolete_views(
        self,
        user_id: str,
        current_key: _ViewKey,
    ) -> None:
        scope_key = self.scope.key
        stale = [
            key
            for key in self._views
            if key != current_key and key[0] == scope_key and key[1] == user_id
        ]
        for key in stale:
            self._drop_view(key)

    def _enforce_view_limits(self, oversized: _AuthorizedView | None = None) -> None:
        """Evict least-recently-used views until both bounds hold.

        A view that is still being used for the current request may be evicted
        here: callers hold their own reference, so it can finish the request
        even though it is no longer retained.

        A single view that exceeds the byte budget on its own is dropped first,
        before any generic LRU eviction.  Otherwise admitting (or lazily
        indexing) one oversized authorized corpus would evict every smaller,
        useful view on its way out and leave the cache colder than it started.
        """

        if (
            oversized is not None
            and self._view_cache_bytes is not None
            and oversized.estimated_bytes() > self._view_cache_bytes
        ):
            self._drop_view_object(oversized)
        while self._views:
            if len(self._views) > self._view_cache_size:
                self._drop_view(next(iter(self._views)))
                continue
            if (
                self._view_cache_bytes is not None
                and self._retained_view_bytes() > self._view_cache_bytes
            ):
                self._drop_view(next(iter(self._views)))
                continue
            break

    def _drop_view_object(self, view: _AuthorizedView) -> None:
        """Drop a specific view by identity, if this cache still holds it."""

        for key, candidate in self._views.items():
            if candidate is view:
                self._drop_view(key)
                return

    def _drop_view(self, key: _ViewKey) -> None:
        view = self._views.pop(key, None)
        if view is not None:
            self._view_evictions += 1
            self._evicted_estimated_bytes += view.estimated_bytes()

    def _retained_view_bytes(self) -> int:
        return sum(view.estimated_bytes() for view in self._views.values())

    def cache_stats(self) -> ViewCacheStats:
        """Return read-only retained-size and eviction accounting.

        The retained bytes are an estimate of the objects the cache holds, not
        a process RSS reading; see :class:`ViewCacheStats`.
        """

        return ViewCacheStats(
            views=len(self._views),
            retained_estimated_bytes=self._retained_view_bytes(),
            evictions=self._view_evictions,
            evicted_estimated_bytes=self._evicted_estimated_bytes,
            max_views=self._view_cache_size,
            max_bytes=self._view_cache_bytes,
        )

    def _view_key(self, user_id: str, token: object | None) -> _ViewKey | None:
        """Bind a retained view to its scope, caller, and live token.

        The documented fast-path token exposes ``doc_epoch`` and
        ``membership_epoch``.  A host may instead return any hashable opaque
        token; binding the key to that value keeps invalidation correct instead
        of silently collapsing every token to ``(0, 0)`` and serving a stale
        memoized view after an edit.  A ``None`` or unhashable token is never
        retained, which degrades to the legacy uncached read.
        """

        if token is None:
            return None
        component = self._token_component(token)
        if component is None:
            return None
        return (self.scope.key, user_id, component)

    @staticmethod
    def _token_component(token: object) -> object | None:
        if hasattr(token, "doc_epoch") or hasattr(token, "membership_epoch"):
            epochs = (
                getattr(token, "doc_epoch", None),
                getattr(token, "membership_epoch", None),
            )
            if not all(type(epoch) is int and epoch >= 0 for epoch in epochs):
                return None
            return ("epochs", *epochs)
        try:
            hash(token)
        except TypeError:
            return None
        return ("opaque", token)

    def _authorized_snapshot(self, user_id: str) -> tuple[KnowledgeDocument, ...]:
        """Read the caller's authorized documents from one consistent view."""

        return self._view(user_id).documents

    def _generate(
        self,
        question: str,
        *,
        user_id: str,
        generate: Generate | None,
    ) -> tuple[dict[str, object], bool]:
        """Generate and revalidate after the callback, never serving a race.

        Returns the payload and whether it must remain uncached. Malformed
        output and exhausted retries produce temporary abstentions; the next
        request must be able to recover when the model or sources stabilize.
        """

        for _ in range(_MAX_ATTEMPTS):
            attempt_scope = self.scope
            view = self._view(user_id, indexed=generate is None)
            fingerprint = view.fingerprint
            try:
                if generate is None:
                    output = self._default_generate(question, view)
                else:
                    output = generate(question, view.documents)
                grounded = parse_answer(question, view.documents, output)
            except MalformedModelOutput:
                return self._abstention(question, user_id), True
            # Re-read after the callback: an edit, delete, ACL revoke, or group
            # change during generation must not yield stale prose.
            current = self._view(user_id)
            if self.scope == attempt_scope and current.fingerprint == fingerprint:
                return self._grounded(grounded, current, question, user_id), False
        return self._abstention(question, user_id), True

    def _grounded(
        self,
        grounded: GroundedAnswer,
        view: _AuthorizedView,
        question: str,
        user_id: str,
    ) -> dict[str, object]:
        by_id = view._by_id
        dependencies = [
            {
                "document_id": evidence.document_id,
                "revision": evidence.revision,
                "content_digest": by_id[evidence.document_id].content_digest,
            }
            for evidence in grounded.evidence
        ]
        return {
            "schema": CACHE_SCHEMA,
            "question": question,
            "user_id": user_id,
            "answer": grounded.answer,
            "disposition": grounded.disposition.value,
            "evidence": [_evidence_record(row) for row in grounded.evidence],
            "dependencies": dependencies,
            "authorized_fingerprint": view.digest,
        }

    def _abstention(self, question: str, user_id: str) -> dict[str, object]:
        view = self._view(user_id)
        return {
            "schema": CACHE_SCHEMA,
            "question": question,
            "user_id": user_id,
            "answer": ABSTENTION_TEXT,
            "disposition": AnswerDisposition.INSUFFICIENT_EVIDENCE.value,
            "evidence": [],
            "dependencies": [],
            "authorized_fingerprint": view.digest,
        }

    def _serve_cached(
        self, payload: Mapping[str, object], *, question: str, user_id: str
    ) -> dict[str, object] | None:
        if not cache_record_matches_request(
            payload,
            schema=CACHE_SCHEMA,
            question=question,
            user_id=user_id,
            scope_key=self.scope.key,
        ):
            return None
        current = self._view(user_id)
        if current.digest != payload.get("authorized_fingerprint"):
            return None
        by_id = current._by_id
        for dependency in payload.get("dependencies") or ():
            document = by_id.get(str(dependency.get("document_id")))
            if document is None:
                return None
            if document.revision != dependency.get("revision"):
                return None
            if document.content_digest != dependency.get("content_digest"):
                return None
        for record in payload.get("evidence") or ():
            document = by_id.get(str(record.get("document_id")))
            if document is None:
                return None
            if document.revision != record["revision"]:
                return None
            if record["quote"] not in document.body:
                return None
            if record.get("start") is not None and (
                document.body[record["start"] : record["end"]] != record["quote"]
            ):
                return None
        return self._present(payload, cache_hit=True)

    @staticmethod
    def _present(
        payload: Mapping[str, object], *, cache_hit: bool
    ) -> dict[str, object]:
        return {
            "answer": str(payload.get("answer") or ""),
            "disposition": str(
                payload.get("disposition")
                or AnswerDisposition.INSUFFICIENT_EVIDENCE.value
            ),
            "evidence": list(payload.get("evidence") or ()),
            "cache_hit": cache_hit,
        }

    def _default_generate(
        self, question: str, view: _AuthorizedView
    ) -> dict[str, object]:
        """Deterministic extractive answer over already-authorized documents."""

        if not view.documents:
            return {
                "answer": ABSTENTION_TEXT,
                "disposition": AnswerDisposition.INSUFFICIENT_EVIDENCE.value,
            }
        refs = view.refs
        for hit in view.index.search(question, limit=1, allowed_refs=refs.keys()):
            if hit.score <= 0.0:
                break
            document = refs[hit.ref]
            quote = self._best_quote(question, document.body)
            return {
                "answer": f"{EXTRACTIVE_LABEL}{quote}",
                "disposition": AnswerDisposition.GROUNDED.value,
                "evidence": [{"document_id": document.document_id, "quote": quote}],
            }
        return {
            "answer": ABSTENTION_TEXT,
            "disposition": AnswerDisposition.INSUFFICIENT_EVIDENCE.value,
        }

    @staticmethod
    def _best_quote(question: str, body: str) -> str:
        sentences = [row.strip() for row in _SENTENCE.findall(body) if row.strip()]
        if not sentences:
            return body.strip()
        terms = set(_WORD.findall(question.casefold()))
        return max(
            sentences, key=lambda row: len(terms & set(_WORD.findall(row.casefold())))
        )

    @staticmethod
    def _cache_key(question: str, user_id: str) -> str:
        payload = canonical_json_bytes({"question": question, "user_id": user_id})
        return "answer:" + hashlib.sha256(payload).hexdigest()
