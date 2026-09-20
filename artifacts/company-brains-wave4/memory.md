> Agent handoff report. See [integrated results](README.md) for coordinator fixes, final measurements, and supported behavior.

# Wave 4: byte-bounded authorized-view cache for many users

Owner: memory builder. Files changed:

- `examples/company_brains/durable/engine.py` (approximate retained-byte budget,
  lazy-index enforcement, obsolete-view eviction, read-only cache stats)
- `tests/test_brain4_memory.py` (new behavioral tests)
- `benchmarks/company_brain_cache_memory.py` (new many-user memory benchmark)

No other source file, test, benchmark, git state, dependency, or credential was
touched. The benchmark writes
`artifacts/company-brains-wave4/memory-benchmark.json`; this report is
`artifacts/company-brains-wave4/memory.md`.

## Problem

Wave 3 bounded the authorized-view cache by **count** only
(`view_cache_size`, default 8). A long-lived brain serving many users could
therefore still pin an unbounded amount of document text: each `_AuthorizedView`
holds the authorized document tuple, its fingerprint tuple, a
`ref -> document` map, and (after first use) a BM25 index. With a count bound of
8, eight users each authorized over a large corpus can retain tens of megabytes,
and nothing in the count bound reacts when the corpus or the visible subset
grows.

## Design

### Approximate retained-byte budget

`CompanyBrain` accepts a new keyword-only
`view_cache_bytes: int | None = None` alongside `view_cache_size`. `None`
disables the byte bound, so the wave-3 constructor contract and behavior are
unchanged.

Each `_AuthorizedView` computes a deterministic retained-size estimate:

- document text fields (ids, title, body, revision, digests, url), ACL
  visibility, and each principal, plus a coarse per-object overhead;
- serialized metadata for non-empty metadata mappings;
- fingerprint strings and a per-ref overhead for the `ref -> document` map;
- when the lazy BM25 index is built, the `title + body` unit text, index
  bookkeeping, and per-unit overhead.

The estimate is deliberately coarse and is **not** RSS, `sys.getsizeof`, or a
hard allocator cap. It is monotonic in content size, which is all the budget
needs, and the budget enforcement uses the exact same estimate that
`cache_stats` reports.

### Enforcement points

`_enforce_view_limits` evicts least-recently-used views until both bounds hold.
It runs:

1. when a view is stored (`_store_view`), and
2. again when a lazily built index grows an already-cached view
   (`_AuthorizedView.index` invokes an `on_index_built` callback wired to the
   brain). A view whose documents fit the budget but whose index does not is
   therefore served for the current request and then dropped, not retained.

A view evicted during its own request is safe: the caller holds a local
reference and the index was already built before eviction. With
`view_cache_bytes=0` (or `view_cache_size=0`) no view is retained, yet every
request still answers correctly.

### Obsolete-view eviction

The view key includes the live `(doc_epoch, membership_epoch)` token. When a
new view is stored for a scope/user, `_evict_obsolete_views` drops every older
view for that same scope/user in the same call, so per-user retention tracks
live state rather than edit history. A long stream of edits no longer
accumulates one dead view per revision.

### Read-only statistics

`CompanyBrain.cache_stats()` returns a frozen `ViewCacheStats`:

```text
views                     currently retained views
retained_estimated_bytes  estimated bytes held by those views (with indexes)
evictions                 total views dropped (LRU, obsolete, or oversized)
evicted_estimated_bytes   estimated bytes dropped
max_views / max_bytes     the configured bounds
```

The dataclass docstring states explicitly that the bytes are an estimate, not an
RSS reading and not a hard process-memory cap.

### Validation and no duplicate maps

Both budget parameters are validated with `_validate_budget`: booleans and
non-integers raise `TypeError`; negatives raise `ValueError`; `None` is allowed
only for `view_cache_bytes`. `_AuthorizedView` stores only the document tuple
and the `ref -> document` map; it does **not** cache a second
`document_id -> document` mapping, because the values would be the same pinned
documents. The by-id lookups in `_grounded` / `_serve_cached` remain transient
per request.

## Tests (`tests/test_brain4_memory.py`)

16 tests pin the contract:

- constructor defaults preserve the count-only wave-3 cache (`max_bytes is None`);
- boolean, negative, and non-integer budgets are rejected; zero is accepted;
- the count bound evicts LRU and reports evictions;
- the byte budget evicts until the retained estimate is under budget;
- building the lazy index re-enforces the budget on an existing view;
- an oversized view serves the request but is not retained;
- zero byte and zero count budgets retain nothing while still answering;
- a token change evicts the obsolete view for the same user;
- the byte budget holds across invalidation;
- a cached lazy index is reused and not rebuilt under a byte budget;
- the view stores no duplicate by-id mapping;
- `cache_stats()` is a frozen snapshot.

Run:

```bash
.venv/bin/ruff check examples/company_brains/durable/engine.py \
  tests/test_brain4_memory.py benchmarks/company_brain_cache_memory.py
.venv/bin/python -m pytest tests/test_brain4_memory.py -q
```

Result: `All checks passed!` and `16 passed`. The broader durable wave-2/3
targeted set (`test_brain2_engine`, `test_brain2_integration`,
`test_brain2_revocation`, `test_brain2_store`, `test_brain3_cache`,
`test_brain3_integration`, `test_brain4_memory`) passes 76/76.

## Benchmark (`benchmarks/company_brain_cache_memory.py`)

Deterministic mixed-ACL corpus (`build_documents` from the scale benchmark:
public / connector_scope / team-restricted) plus deterministic users with mixed
group memberships. 240 documents, 96 users, 4 queries per user = 384 searches.
`build_user_queries` and `build_users` are seeded by `hashlib` per entity, so the
corpus is identical for a fixed seed.

Each request reports retained estimated bytes, tracemalloc actual retained and
peak, misses (authorized-view rebuilds, counted as one `access_token_snapshot`
read each), hits, hit rate, and evictions. **No machine-time threshold is
applied**; `elapsed_seconds` is informational only.

From `memory-benchmark.json`:

| scenario | bound (views / bytes) | retained views | retained est. bytes | tracemalloc retained | tracemalloc peak | evictions | hits / misses / rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| count + byte bounded | 12 / 3,145,728 | 10 | 3,081,190 | 11,568,635 | 12,379,082 | 86 | 288 / 96 / 0.75 |
| count bound only | 16 / none | 16 | 4,947,828 | 18,386,067 | 19,279,193 | 80 | 288 / 96 / 0.75 |
| zero byte budget | 12 / 0 | 0 | 0 | 300,608 | 1,574,671 | 384 | 0 / 384 / 0.00 |

The byte bound retains ~38% fewer estimated bytes (3.08 MB vs 4.95 MB) and ~37%
less actual tracemalloc-retained memory (11.6 MB vs 18.4 MB) than the count bound
alone at the same 75% hit rate: every user's four consecutive queries still hit
after the first. With a zero byte budget nothing is retained (in-bounds), every
request rebuilds, and every request still returns a correct answer.

The two memory numbers measure different things and are reported separately.
`retained_estimated_bytes` is the engine's object-size estimate over exactly the
cached views. `tracemalloc.retained_bytes` / `peak_bytes` are actual traced
allocations made while tracing (brain, retained views, indexes, and transient
BM25 work); the corpus and durable rows were built before the tracing window.
The estimate is lower than tracemalloc actuals, as expected, because the BM25
internals and shared strings are not fully modeled.

Run:

```bash
.venv/bin/python -m benchmarks.company_brain_cache_memory --output /tmp/memory.json
.venv/bin/python -m benchmarks.company_brain_cache_memory --no-byte-budget \
  --view-cache-size 16
.venv/bin/python -m benchmarks.company_brain_cache_memory --view-cache-bytes 0
```

## Baseline and wave interactions

Baseline was 994 collected tests. After this work the full suite collected 1070;
excluding two intentionally-red adversarial files added by a sibling wave and a
docs test affected by a sibling's new `docs/agents/email.md`, the suite passes
1032/1032. The failures are not caused by this change:

- `tests/test_brain4_adversarial.py` states in its own docstring that several
  tests are expected to fail against the current implementation and are recorded
  as bugs in `artifacts/company-brains-wave4/adversarial.md`; it never edits
  source.
- `tests/test_brain4_integration.py` asserts the same desired cache-record
  validation (wrong question/user/evidence revision) that the adversarial suite
  records as a divergence. Making `_serve_cached` reject those records is a
  separate hardening task, deliberately not part of this memory change.
- `tests/test_documentation_evidence.py` fails on a sibling's new
  `docs/agents/email.md`, unrelated to the durable engine.

## Limits

The byte bound is an estimate, not a byte-exact cap: no Python process can
exactly bound retained memory without an allocator hook. The count bound still
applies and is still the cheapest guard. The budget is per `CompanyBrain`
instance in one process and is not a distributed or cross-process cache, exactly
as in wave 3. Correctness (fresh token reads, cross-connection invalidation,
callback revalidation, persisted-payload validation) is unchanged.
