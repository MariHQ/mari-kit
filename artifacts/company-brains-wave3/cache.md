> Agent handoff report. See [integrated results](README.md) for subsequent coordinator fixes and final measurements.

# Wave 3: cheap durable access tokens and bounded snapshot caching

Owner: cache builder. Files changed:

- `examples/company_brains/durable/store.py` (durable epochs, token API)
- `examples/company_brains/durable/engine.py` (bounded authorized-view cache)
- `tests/test_brain3_cache.py` (new behavioral tests)

No other file, git state, dependency, or credential was touched.

## Problem

Wave 2 reads and re-authorizes the full document set, then rebuilds a BM25
index, on every `search` and every `answer` revalidation. For an unchanged
brain that is repeated, unnecessary durable work: the same rows are decoded and
the same index is constructed for every request.

The hard part is doing that safely. A naive cache is wrong in two ways:

1. **Stale tagging.** If the engine reads a snapshot and *then* reads a newer
   change counter, it can label old documents with a new counter and later
   serve revoked content.
2. **Missed invalidation.** In-memory caches cannot notice ACL, title, delete,
   or group changes made by another connection unless a durable signal advances.

## Design

### Durable epochs (store.py)

Two monotonic counters are persisted and bumped inside the same transaction as
the change they describe:

- `scope_epochs(tenant, space, doc_epoch)` — advanced by `apply_plan` whenever
  the plan actually contains upserts or tombstones (including same-revision ACL
  and metadata observations). A state-only synchronization that plans zero
  changes does **not** advance it.
- `membership_epochs(tenant, space, user_id, membership_epoch)` — advanced by
  `set_groups` only when the normalized group set actually changes. Re-setting
  the same groups is a no-op.

Because the bumps share the writer transaction, a crash or failed plan rolls
them back with the documents and state, so epochs never describe an unwritten
change.

### Cheap access token

`AccessToken(doc_epoch, membership_epoch)` is a frozen value. Two store
methods expose it:

```text
access_token(scope, user_id) -> AccessToken
    One SELECT over the two epoch rows. It never loads document payloads.

access_token_snapshot(scope, user_id)
    -> (AccessToken, tuple[KnowledgeDocument, ...], frozenset[str])
    Reads the token and the document/group rows inside one read transaction.
```

`access_token_snapshot` is the consistency primitive. The token and the rows
come from the same SQLite read snapshot, so a caller can safely memoize the
rows under the token: it can never associate a newer token with an older
snapshot, nor an older token with newer rows. The legacy
`access_snapshot(scope, user_id) -> (documents, groups)` is unchanged and still
used by stores that do not implement the token API.

### Bounded authorized-view cache (engine.py)

`CompanyBrain` keeps an `OrderedDict` keyed by
`(user_id, token.doc_epoch, token.membership_epoch)` holding an
`_AuthorizedView`: the authorized documents, their fingerprint, a
`ref -> document` map, and a lazily built `RevisionBM25Index`.

Request flow (`_view`):

1. Read the cheap token with `access_token`.
2. On a cache hit, return the memoized view: no document rows, no index build.
3. On a miss, call `access_token_snapshot` for a transactionally consistent
   `(token, documents, groups)`. Re-key on *that* token, build the view, and
   store it. The probe token is never used to tag the snapshot.
4. If the store lacks both token methods, fall back to `access_snapshot` and
   build an uncached view.

The cache is bounded (`view_cache_size`, default 8); the least-recently-used
entry is evicted, so a long-lived brain serving many users does not grow
without limit. The BM25 index is built on first use of a view, so a
host-supplied `generate` callback never pays for an index it will not use,
while a second `search` or extractive `answer` for the same token reuses it.

`search`, `_serve_cached`, `_generate`, `_grounded`, and `_abstention` all read
through `_view`, so the same snapshot is reused across the checks that make up a
single request. Persisted payload validation is unchanged: the stored
`authorized_fingerprint`, per-evidence `revision`/`content_digest`, and quote
containment are still checked against the current authorized view before a
cached answer is served.

## Why it is safe

- **No stale tagging.** The view is always built from a token read in the same
  transaction as its rows. Epochs are monotonic, so a token never recurs once
  superseded.
- **Cross-connection invalidation.** Any committed document/ACL/delete change
  bumps `doc_epoch`; any committed group change bumps that user's
  `membership_epoch`. A reader connection observes the new epoch on its next
  cheap read and misses the cache, forcing a fresh authorized view.
- **Callback revalidation preserved.** `_generate` keeps its wave-2 loop:
  capture the fingerprint, run the callback, re-read through `_view`, and only
  serve when the fingerprint is unchanged. A revoke/edit during generation
  advances the token and the recheck fails.
- **Legacy stores.** Detection uses `getattr`; when the token methods are
  absent the engine behaves exactly like wave 2 (full read per request), still
  correctness-safe.

## Tests (`tests/test_brain3_cache.py`)

- token is cheap, consistent with `access_token_snapshot`, and only advances on
  real document/membership changes (not state-only syncs or repeated groups);
- a repeated `search` does not reload documents (counted snapshot reads);
- a new question reuses the memoized view and the single BM25 build;
- membership revocation invalidates a cached answer;
- same-revision ACL change advances the token and revokes;
- title-only edit advances the document epoch and changes results;
- a second SQLite connection's edit/revocation invalidates the view;
- a callback race is still never served from stale prose;
- deletion invalidates the view;
- the view cache is bounded per brain;
- a store without the token API still authorizes, caches answers, and revokes.

Run:

```bash
.venv/bin/python -m pytest tests/test_brain3_cache.py -q
.venv/bin/ruff check examples/company_brains/durable/store.py \
  examples/company_brains/durable/engine.py tests/test_brain3_cache.py
```

Full wave-2 durable/engine/revocation/store/crash/integration suites still pass.

## Limits

Caching is per `CompanyBrain` process and is not a distributed cache. Correctness
relies on the token reads being cheap and current; a change committed after the
winning token read is subject to the same delivery window the wave-2 engine
already had (a completed read observes a consistent snapshot; a later
revocation does not retract an answer already computed). Hardware power loss,
backup/restore, and multi-writer service deployment remain outside this example.
