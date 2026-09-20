> Agent handoff report. See [integrated results](README.md) for final validation and publication handling.

> Agent handoff report. See the coordinator's integrated results for final
> measurements and supported behavior.

# Wave 5: compact authorized digests and precomputed view maps

Owner: `cache` agent. Files changed:

- `examples/company_brains/durable/engine.py`
- `examples/company_brains/durable/cache_records.py`
- `tests/test_brain5_cache.py` (new, 18 tests)
- `artifacts/company-brains-wave5/cache.md` (this report)

No other source file, test, benchmark, dependency, credential, network access,
or git state was touched. No benchmark was edited.

## Problem

Wave 3/4 memoized an authorized view under a cheap live access token and bounded
the view cache by count and estimated retained bytes. Two costs remained on the
hot path:

1. **Persisted records grew with the corpus.** The answer record stored the full
   ordered `authorized_fingerprint` list — one 64-character entry per authorized
   document. A grounded answer citing one document from a 150-document
   authorized view persisted ~10 KB of unrelated fingerprints, even though the
   user never saw those documents.
2. **Every cache hit rebuilt an O(N) map.** `_grounded` and `_serve_cached`
   constructed `{document.document_id: document for document in docs}` on each
   request to resolve citations, revalidate dependency `content_digest`s, and
   check exact quotes.

## Design

### Compact digest (schema v3)

`CACHE_SCHEMA` is bumped to `company-brain-answer-v3`. The persisted
`authorized_fingerprint` field now holds **one fixed-width SHA-256 digest** of
the whole authorized set:

- `fingerprint_digest(fingerprint)` hashes the ordered per-document fingerprint
  tuple (the existing `authorized_fingerprint` output) with
  `canonical_json_bytes`.
- `authorized_digest(documents)` is the public convenience form.
- `authorized_fingerprint(documents)` is **unchanged** and still returns the
  ordered `tuple[str, ...]` of per-document fingerprints, so any host or test
  that imports it keeps working.

The digest is computed **once**, in `CompanyBrain._build_view`, and stored on the
view as `digest`. `_grounded` and `_abstention` persist `view.digest`; they no
longer copy `list(view.fingerprint)` into the record.

Because the digest covers the same material as `document_fingerprint` (revision,
provider revision, content digest, title, body, updated_at, source URL, ACL, and
metadata), a same-revision title, ACL, or metadata edit changes the digest and
invalidates a cached record. Body and revision changes obviously do too.

### Legacy v1/v2 regeneration

No migration code is needed: `cache_record_matches_request` rejects any record
whose `schema` is not v3 before any other check, so a v1/v2 record is a clean
cache miss. The request then regenerates and overwrites the same cache key with a
v3 record. This is exercised for both the old list fingerprint and a digest
under both legacy schema strings.

### Precomputed by-id map

`_AuthorizedView` now retains a private `_by_id` map built once alongside `refs`.
It points at the same pinned `KnowledgeDocument` objects as `documents`/`refs`,
so `_grounded` and `_serve_cached` resolve citations in O(1) per cited document
with no per-request construction. The map is charged through the existing
`_retained_size` traversal, which deduplicates by object identity; only the dict
container and its key strings are added to the retained-byte estimate, and the
existing count/byte bounds re-enforce as before. The map uses a private name
(`_by_id`) so the wave-4 guard that forbids a public duplicate `by_id` slot
continues to hold.

### Validation preserved

`_serve_cached` still, on every request:

- checks schema, checksum, scope, question, user, disposition, and record shape
  through `cache_record_matches_request`;
- reads the **live** access token via `self._view(user_id)` (so a cross-
  connection membership or document epoch change is observed);
- compares the live digest to the persisted digest;
- re-resolves each dependency by id and rechecks `revision` and
  `content_digest`;
- re-resolves each evidence row by id and rechecks `revision`, that the quote is
  a substring of the live body, and that any `start`/`end` span reproduces the
  quote exactly.

`_generate` still re-reads the view after the model callback and compares the
fingerprint tuple (`current.fingerprint == fingerprint`) before serving, so an
edit, delete, ACL revoke, or group change during generation cannot produce stale
prose.

## Tests

`tests/test_brain5_cache.py` adds 18 tests:

- schema is v3 and the persisted field is a 64-character lowercase-hex digest
  equal to `authorized_digest`;
- a 150x larger unrelated authorized corpus produces a byte-identical stored
  record (only the fixed-width digest is corpus-dependent material);
- repeated cache hits do not re-invoke `authorized_fingerprint` or
  `fingerprint_digest` and reuse the same view and `_by_id` map identity;
- the view's `_by_id` values are the same objects as `documents`;
- legacy v1/v2 records (list and digest fingerprints) are safe misses that
  regenerate as v3;
- missing/empty/list digests are never served;
- cross-connection revocation and a follow-up edit invalidate the cached answer
  while reusing the view cache for stable requests;
- same-revision title, metadata, and ACL edits change the digest and invalidate
  a persisted record even with token memoization disabled;
- tampered dependency `content_digest`, non-substring quote, and mismatched
  quote offsets are all cache misses;
- `authorized_fingerprint` still returns the ordered tuple.

## Verification

- `examples/company_brains/durable/engine.py`,
  `examples/company_brains/durable/cache_records.py`, and
  `tests/test_brain5_cache.py`: `ruff check` clean.
- `tests/test_brain5_cache.py`: 18 passed.
- Full suite (`.venv/bin/python -m pytest -q`): **1102 passed** (1079 baseline
  plus the new file and concurrently added tests).

## Notes / residual

- The persisted field keeps the name `authorized_fingerprint` but now carries a
  string digest. This preserves the wave-4 adversarial test that removes the
  field to prove a missing-fingerprint record is rejected, and keeps the
  "missing fingerprint must not match an empty set" invariant.
- A v3 record without dependencies/evidence is still structurally rejected for a
  grounded disposition by `cache_record_matches_request`; server-side
  dependencies remain the freshness anchor.
- The digest is unkeyed, like the existing checksum. It detects change and
  accidental corruption, not a malicious writer with database access.
