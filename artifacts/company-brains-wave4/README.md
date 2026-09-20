# Company brains: fourth wave

Three parallel OpenCode `deepseek/deepseek-flash` agents implemented bounded
cache memory, multi-start retrieval, and adversarial lifecycle tests. The
coordinator integrated fixes, added independent regressions, reran measurements,
and exercised the real model against the durable application.
[Agent sessions](sessions.json). All changes remain local and uncommitted.

## Changes and fixes

- `CompanyBrain(..., view_cache_bytes=...)` enforces an estimated retained-byte
  limit alongside the existing view-count limit. Limits apply again after lazy
  index construction. Oversized views can serve the current request but are not
  retained; obsolete versions of a user's view are evicted. `cache_stats()`
  returns immutable accounting. Defaults preserve count-only retention.
- The coordinator replaced a coarse text-size estimate after measurements showed
  substantial undercounting. Accounting now traverses Python value and index
  containers, including tokens and weights, deduplicating objects within each
  view. Shared objects across views are counted conservatively. This remains an
  estimate, not an RSS or peak-allocation cap.
- `HNSWIndex.search(search_starts=8)` merges deterministic authorized traversals.
  The default single-start behavior is preserved, including existing recall.
  A regression test caught quadratic level scanning in the initial selector;
  the builder fixed it and avoids sorting additional starts on the default path.
- Cache schema v2 validates question/user/scope binding, disposition, evidence,
  dependencies, revisions, quote offsets, and source freshness. An unkeyed
  checksum detects accidental modifications to otherwise plausible records.
  Malformed JSON and malformed records become regenerable cache misses.
  Existing v1 records are regenerated once; durable source data is unchanged.
- Scope changes during a model callback force re-generation under the new scope,
  even if both tenants have identical source text and fingerprints. Repeated
  changes exhaust the normal retry limit and return an uncached abstention.
- Fixed two documentation-content checks for the email page added in wave 3:
  a direct section heading and a public API example. Regenerated the source
  inventory and passed the strict documentation build.

The adversarial suite exercises five seeded randomized histories, two SQLite
connections, multiple scopes and users, edits, deletes, memberships, restarts,
and rollback against a freshly computed independent retrieval oracle. It also
tests malformed/misbound cache records and callback scope changes. The final
suite has no skipped expected failures for these cases.

## Memory measurements

240 mixed-ACL documents, 96 users, four consecutive queries per user, 384 total
requests. All configurations use the same 16-view count limit. Allocation
tracing starts after corpus and store setup. [Raw comparison](memory-final.json).

| Byte policy | Retained views | Estimated retained | Traced retained | Traced peak | View-cache hit rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| No byte limit | 16 | 16.75 MiB | 17.96 MiB | 19.42 MiB | 75% |
| 3 MiB budget | 2 | 2.15 MiB | 2.87 MiB | 5.22 MiB | 75% |
| Zero budget | 0 | 0 | 0.66 MiB | 2.86 MiB | 0% |

The 3 MiB estimated budget reduced traced retained allocations by about 84% in
this workload. The observed hit rate depends on consecutive queries by each
user; interleaving many users can cause more eviction and fewer hits. Zero
retention still incurs temporary snapshot/index work and non-cache allocations.
These measurements are not concurrent request load tests.

The earlier [agent measurement](memory-benchmark.json) used coarse accounting
and different count limits; it is preserved as historical evidence, not used
for this comparison.

## Retrieval measurements

1,000 deterministic vectors, 20 queries, cosine metric, `k=10`, `ef_search=64`,
exact fallback disabled. Every row uses the same query and permission masks.
[Final benchmark](retrieval-final.json).

| Allowed IDs | Starts | Recall | Mean query time |
| --- | ---: | ---: | ---: |
| 200 | 1 | 49/200 (24.5%) | 0.145 ms |
| 200 | 4 | 96/200 (48%) | 0.378 ms |
| 200 | 8 | 113/200 (56.5%) | 0.576 ms |
| 1,000 | 1 | 144/200 (72%) | 0.270 ms |
| 1,000 | 4 | 178/200 (89%) | 1.023 ms |
| 1,000 | 8 | 180/200 (90%) | 1.312 ms |

No unauthorized hits. Multi-start search remains approximate and costs more
work; the prior wave's exact fallback is still preferable when exact scoring of
a small allowed set is affordable. An engaged exact fallback takes precedence
over multi-start. For legacy compatibility, `ef_search` is checked between
neighbor batches; it is not a strict total-score budget, and greedy descent
performs additional scoring.

## Validation

**1,079 tests pass**, up from 994 at the start of this wave. Ruff lint/format,
Pyright, wheel/sdist build, installed-wheel durable demo, original examples,
all eight first-wave scenarios, strict Sphinx build, generated inventory check,
and browser sidebar checks pass.

The real DeepSeek Flash durable workflow passed all ten lifecycle checks with
seven answer calls and seven extraction calls. This exercises restart, warm
cache, source edit, membership revocation, same-revision ACL change, new grants,
deletion, and projection consistency. [Live results](live-durable.json),
[deterministic results](durable-fixture.json).

The [scale run](scale-final.json) retains the prior workload for checking warm
performance after cache validation and memory-accounting changes. At 25,000
documents, search p95 was 250 ms and cached-answer p95 was 32 ms, versus 231 ms
and 23 ms in wave 3. The new checks add work; timings also vary between local
runs. Cache records still contain the full authorized-fingerprint list, so
validation is not O(1). This wave did not create a new static answer-quality
corpus; wave 3's quality results remain separate.

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m examples.company_brains.durable
.venv/bin/python -m benchmarks.company_brain_cache_memory --documents 240 \
  --users 96 --view-cache-size 16 --view-cache-bytes 3145728 \
  --output /tmp/brain-memory.json
.venv/bin/python -m benchmarks.company_brain_multistart --size 1000 \
  --queries 20 --allowlist-sizes 200 1000 --search-starts 1 4 8 \
  --output /tmp/brain-retrieval.json
```

## Boundaries

The database and its writers remain trusted. The checksum is not authentication:
a writer that changes the answer and recomputes the checksum can still write
unsupported prose. Exact citations do not prove semantic entailment. A valid
abstention may include evidence; that behavior is supported by the core answer
contract, despite a contrary interpretation in the agent handoff notes.

All writers must maintain access counters through the updated store methods.
Database replacement/restore requires new brain instances. Memory budgets cover
retained views, not temporary work, source storage, or total process RSS.
Approximate full-corpus recall, a production retrieval adapter, and concurrent
service deployment remain open work.
