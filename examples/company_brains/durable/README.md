# Persistent company brain

A host-owned reference application composes Mari Kit with Python's SQLite
driver. It keeps live documents, a search projection, sync state, memberships,
and answer caches across restarts. Mari Kit remains backend-agnostic.

Run the deterministic lifecycle with a temporary database:

```bash
python -m examples.company_brains.durable
```

Or retain the synthetic `durable-demo` tenant in a database you choose:

```bash
python -m examples.company_brains.durable --db /tmp/company-brain.sqlite
```

The demonstration verifies restart/cache reuse, membership revocation, policy
edits, ACL changes without a provider revision bump, deletion, and projection
consistency. Rerunning seeds and exercises that same synthetic tenant again.

## Persistence and access

`SQLiteBrainStore.apply_plan` uses one SQLite transaction for live documents,
the durable text projection, and source checkpoints. It checks the expected
generation inside the write transaction. Process-death tests terminate workers
after document writes, after projection writes, before commit, and after commit,
then verify state from a fresh process.

`CompanyBrain` takes a trusted tenant scope and user ID. The host policy allows
tenant-visible documents plus restricted documents granted to the user or their
current groups. It checks live access counters on every request and checks sources
again after a model callback. Cache reuse requires matching authorized source
observations. Same-revision ACL changes update the live observation while
historical observations are retained separately.

Document and membership counters advance in the same transaction as their
changes. The engine reuses authorized snapshots and BM25 indexes while counters
match, with at most eight cached views by default (`view_cache_size` controls
this bound). Cache keys include tenant, space, user, and both counters. Stores
without the counter API retain the original snapshot-read behavior. All writers
must use the updated store methods; raw SQL or older application writers bypass
counter maintenance. Close brain instances before replacing/restoring a database.

Hosts can also bound retained Python-object size and inspect eviction counts:

```python
brain = CompanyBrain(store, scope, view_cache_size=8, view_cache_bytes=32 * 1024**2)
stats = brain.cache_stats()
```

The byte estimate traverses documents, references, tokens, and index containers,
deduplicating shared objects within a view. It counts sharing across views
conservatively and excludes allocator overhead and temporary allocations. It is
not an RSS cap. Limits are enforced again after a lazy index build; an oversized
view can finish its request but is not retained. Obsolete versions of a user's
view are evicted when that user's access counters change. `None` retains the
original count-only policy, while zero disables view retention.

Search misses build their required index before admission, so an oversized
indexed view is rejected before it can displace smaller warm views. A cached
view that later grows past the byte budget is removed before general LRU
eviction. Callback-only answers still keep index construction lazy. Cache hit
rates depend on request ordering: interleaving more users than the cache holds
can eliminate the reuse observed in consecutive-user benchmarks.

Persisted answer records now use schema v3, with explicit scope/question/user
binding, structural validation, and an unkeyed checksum. Malformed records and
old v1/v2 records are regenerated. The checksum detects accidental record changes;
it does not authenticate cache writers or establish semantic truth. Valid
evidence-backed abstentions remain cacheable. A fixed-size SHA-256 digest
represents the authorized source set; cached views precompute document-ID
lookups. Warm hits check live access counters and cited sources without scanning
the authorized corpus. Invalidated or cold views still load and fingerprint
their authorized documents. If a callback changes the brain's
scope, generation retries against the new scope even when the source text is
identical; repeated scope changes exhaust the normal retry limit.

Authentication, identity provisioning, backup/restore operations, encrypted
storage, retention policy, and service deployment are outside this example.
SQLite atomicity tests exercise process death, not hardware power loss or a
distributed database. A completed read observes a consistent snapshot; a later
revocation does not retract an answer already delivered.

## Answer quality

The quality corpus covers current and superseded policy, unresolved conflicts,
ambiguous questions, missing information, restricted evidence, and irrelevant
matches. Fixture evaluation uses a deterministic baseline. Live evaluation makes
actual DeepSeek Flash calls for both extraction and answering:

```bash
python -m examples.company_brains.durable.quality_eval
python -m examples.company_brains.durable.live_eval --live \
  --output artifacts/company-brains-wave2/live-quality.json
python -m examples.company_brains.durable.live_eval --live \
  --durable-db /tmp/live-company-brain.sqlite \
  --output artifacts/company-brains-wave2/live-durable.json
```

Live mode requires `DEEPSEEK_API_KEY`. It sends only synthetic questions and
host-authorized source revisions. Grading labels stay local. Reports retain all
cases, including request failures, and separate citation validation, lexical
answer-correctness proxies, abstention, and stale answers. Exact citation
validation and lexical grading do not prove semantic entailment.

The `--durable-db` mode runs the same restart/edit/revocation/deletion lifecycle
through the real model callback and the persistent answer engine. It reports
actual model calls separately from cache hits. The engine validates citations
and authorization; prose returned by a custom callback still needs the host's
semantic evaluation policy.

The third-wave corpus adds explicit authority, visible superseded sources,
regional rules, and source prompt injections. It is hashed before evaluation:

```bash
python -m examples.company_brains.durable.quality_wave3 --live \
  --output artifacts/company-brains-wave3/live-quality.json
```

## Scale and recall

```bash
python -m benchmarks.company_brain_scale --sizes 1000 10000 25000 \
  --queries 30 --no-tracemalloc \
  --output artifacts/company-brains-wave2/scale.json
python -m benchmarks.company_brain_recall --size 1000 --queries 20 \
  --output artifacts/company-brains-wave2/recall.json
```

The scale report separates durable writes, cold index construction, warm index
queries, authorization-filtered queries, and batch edit/delete work. Engine
queries include database and application overhead. Allocation tracing changes
timings; use a separate traced run for Python allocation measurements. Process
peak RSS is a high-water mark, not per-operation allocated memory.

The durable projection stores text, not a persisted BM25 data structure. The
reference index is rebuilt as needed. These measurements identify where a
production search adapter is warranted; they do not establish production SLAs.

For sparse vector allowlists, opt into exact fallback with
`HNSWIndex.search(..., exact_filter_threshold=200)`. This scores only authorized
vectors when at most 200 indexed IDs are allowed. The default remains approximate.

```bash
python -m benchmarks.company_brain_filtered_recall --size 1000 --queries 20 \
  --allowlist-sizes 10 50 200 1000 --exact-filter-threshold 200 \
  --output artifacts/company-brains-wave3/filtered-recall.json
```

For larger allowlists, `search_starts=8` combines eight deterministic authorized
graph traversals. Recall improves at additional query cost; it remains
approximate. `search_starts=1` preserves the default behavior, and an engaged
exact fallback takes precedence. The legacy expansion checks `ef_search`
between neighbor batches, rather than enforcing a strict total-score budget.

```bash
python -m benchmarks.company_brain_multistart --size 1000 --queries 20 \
  --allowlist-sizes 200 1000 --search-starts 1 4 8 \
  --output artifacts/company-brains-wave4/retrieval-final.json
python -m benchmarks.company_brain_cache_memory --documents 240 --users 96 \
  --view-cache-size 16 --view-cache-bytes 3145728 \
  --output artifacts/company-brains-wave4/memory-example.json
```

See the [third-wave results](../../../artifacts/company-brains-wave3/README.md)
[fourth-wave results](../../../artifacts/company-brains-wave4/README.md),
and [fifth-wave results](../../../artifacts/company-brains-wave5/README.md)
for measured changes and remaining limits.

The [sixth-wave results](../../../artifacts/company-brains-wave6/README.md)
cover oversized admissions, malformed-record recovery, and interleaved traffic.
