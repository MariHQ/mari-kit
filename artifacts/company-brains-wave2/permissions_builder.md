> Integration note: this is an agent report from the development run. See [the integrated results](README.md) for final fixes, measurements, and verification.

# Wave 2 — permissions builder report

Owner: permission builder (`engine.py`, `tests/test_brain2_engine.py`).
Scope: host authorization, answer generation/caching, and revalidation for the
durable company brain. `store.py` was **not** modified.

## Files

- `examples/company_brains/durable/engine.py` — `CompanyBrain` contract:
  - `search(query, *, user_id, limit=5) -> tuple[KnowledgeDocument, ...]`
    reads one `store.access_snapshot`, applies host policy, builds a
    per-request `RevisionBM25Index` over authorized documents only, and returns
    positive-scoring hits in BM25 rank order.
  - `answer(question, *, user_id, generate=None) -> dict` with exactly
    `answer`, `disposition`, `evidence` (JSON list), `cache_hit`.
  - Default generator is a labeled deterministic extractive answer
    (`"Deterministic extractive answer: " + best sentence`); no positive hit
    yields `insufficient_evidence`.
  - `generate(question, documents)` receives only authorized documents and its
    output is validated with `mari_kit.knowledge.parse_answer`, so it cannot
    cite hidden sources.
  - Cached and freshly generated answers are revalidated immediately before
    serving against a freshly read authorized fingerprint.
- `tests/test_brain2_engine.py` — 11 behavioral tests against the real
  `SQLiteBrainStore`: explicit policy, per-request reads, persisted cache,
  callback validation, callback race, edit/delete/same-revision ACL/group
  changes, current-revision search.

## Policy implemented (explicit)

- `public` and `connector_scope` documents are tenant-visible.
- `restricted` documents require a `Principal(kind="team", identifier=g)` where
  `g` is one of the caller's current store groups, **or** a
  `Principal(kind="user", identifier=user_id)` matching the caller.
- Principal kind is not interchangeable with identity (a `team` named `alice`
  does not authorize user `alice`, and a `user` named `security` does not
  authorize group member `security`).
- Authorization is read from the store on every request; nothing is cached in
  the `CompanyBrain` instance.

## Cache and revalidation design

- Cache key: `sha256(canonical_json({question, user_id}))`, stored through
  `store.save_cache(scope, key, payload)`; scope isolation is the store's.
- Payload holds the answer, disposition, evidence records, per-dependency
  `{document_id, revision, content_digest}`, and an `authorized_fingerprint`
  over **all** currently authorized documents (document_id, revision,
  content_digest, visibility, principals, metadata).
- Serving a cached answer requires the current authorized fingerprint to match
  and every evidence quote to still be present in the current body. This makes
  edits, deletes, same-revision ACL changes, and group membership changes
  invalidate cached output.
- Generation takes an authorized snapshot, calls the generator, validates with
  `parse_answer`, then re-reads the store. If the fingerprint changed during the
  callback, it retries (max 3); if it never stabilizes it returns a safe
  abstention rather than any pre-change prose.
- Malformed generator output (including hidden-source citations) returns an
  uncached abstention, so a corrected callback can succeed on the next request.

## Commands and results

```
.venv/bin/ruff check examples/company_brains/durable/engine.py tests/test_brain2_engine.py
# All checks passed!

.venv/bin/python -m pytest tests/test_brain2_engine.py -q
# 11 passed

.venv/bin/python -m pytest \
  tests/test_brain2_engine.py tests/test_brain2_revocation.py \
  tests/test_brain2_access_review.py -q
# 45 passed

.venv/bin/python -m examples.company_brains.durable
# passed: true (all 10 lifecycle checks true)
```

The two reviewer suites (`test_brain2_revocation.py`,
`test_brain2_access_review.py`) exercise the same engine from the outside and
pass unmodified; they cover group revocation, same-revision ACL revoke,
public→restricted change, deletion, callback races, mixed/uncited hidden
citations, tenant-scoped cache keys, long-lived readers observing another
connection's edit, and principal-kind confusion.

## Defects vs host responsibilities

Engine defects: **none found** by my tests or the reviewer suites.

Host-side hazards surfaced during integration (not engine bugs):

1. `KnowledgeDocument.content_digest` is derived in `__post_init__`.
   `dataclasses.replace(doc, body=..., revision=...)` reuses the old digest and
   raises `ValueError: document content_digest does not match body` whenever the
   body changes. An earlier revision of the sibling
   `examples/company_brains/durable/__main__.py` did this; it now passes
   `content_digest=""`. Recommended fix for any host constructing revisions:
   ```python
   replace(doc, body=new_body, revision="v2", content_digest="")
   ```
   or build a fresh `KnowledgeDocument`. My tests do the same.
2. Trusted identity is a host responsibility. `user_id` is caller-supplied and
   must come from authenticated session context bound to `scope.tenant`.
   Passing an untrusted `user_id` could match a `user` principal or a store
   group. The engine deliberately does not authenticate.
3. The store is the only source of truth for documents, groups, and cache; the
   engine holds no authorization state. A host must not interleave its own
   uncommitted document state as if it were authorized.

## Recommended fixes

- No engine change required for the shared contract.
- Host revision construction: always clear `content_digest` (or reconstruct)
  when changing `body`.
- Callers: pass the trusted `user_id` from authentication; never from request
  input. Keep one `CompanyBrain` per `ScopeRef`; reuse across requests is safe.

## Limitations and design trade-offs

- Conservative invalidation: the fingerprint covers every authorized document
  in the scope, so an unrelated authorized-document edit invalidates all cached
  answers for that scope. This favors correctness over cache efficiency.
- The index is rebuilt per `search`/default-answer from the authorized snapshot,
  so BM25 corpus statistics never include hidden documents, but per-request cost
  is O(authorized corpus). The scale builder should measure rebuild cost; this
  engine does not maintain a durable incremental index.
- Revalidation retries are bounded (3). A generator that mutates the store on
  every invocation yields a safe abstention rather than an answer.
- Malformed generator output is never cached, so a persistently malformed
  callback is re-invoked on every request; this is intentional so a fixed
  callback can recover.
- `answer` returns exactly the four contract keys; `question`, `dependencies`,
  and `authorized_fingerprint` exist only inside the persisted cache payload.
- Authorization here is ACL observation only; it does not model revocation
  lists, time-of-check/time-of-use across the host's authentication layer, or
  semantic answer correctness.
