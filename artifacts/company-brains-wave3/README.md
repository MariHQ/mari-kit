# Company brains: third wave

Three parallel OpenCode `deepseek/deepseek-flash` agents implemented durable
cache reuse, sparse-filter retrieval, and a fresh quality corpus. The coordinator
reviewed the changes, added independent integration tests, ran live evaluation,
and measured the final implementation. [Agent sessions](sessions.json).

## Changes

- SQLite scope-document and per-user membership counters advance atomically with
  writes. A consistent counter/snapshot read feeds a bounded in-memory cache of
  authorized documents, fingerprints, and lazily built BM25 indexes. Unchanged
  requests still check live counters but avoid full document reads and rebuilds.
- The coordinator caught and fixed a tenant-switch cache collision: view keys
  now include tenant/space as well as user and counters. Regression tests cover
  scope switching, rollback, committed edits, and warm SQL reads. Search also
  requests only the required result count instead of materializing every hit.
- `HNSWIndex.search(exact_filter_threshold=200)` optionally uses exact scoring
  when an explicit allowlist contains at most 200 indexed IDs. It scores only
  allowed vectors. The default remains approximate and backward compatible.
- A new 16-case synthetic corpus includes explicit source authority, regional
  rules, visible old and new policies, missing facts, restricted evidence, and
  prompt injections embedded in source documents.
- Regenerated the algorithm inventory after its CI freshness check detected
  stale source declarations from the accumulated implementation changes.
- Added the missing email-guide page to the documentation navigation, resolving
  a broken cross-reference found by the strict Sphinx build.

## Performance

Same deterministic corpus, 20 query samples per size, allocation tracing off.
These are local sequential measurements, not concurrent service load tests.

| Documents | Search p95 before | Search p95 after | Cached answer p95 before | Cached answer p95 after |
| --- | ---: | ---: | ---: | ---: |
| 1,000 | 24.0 ms | 4.1 ms | 21.2 ms | 0.9 ms |
| 10,000 | 302.6 ms | 42.7 ms | 262.6 ms | 8.7 ms |
| 25,000 | 778.1 ms | 231.2 ms | 665.7 ms | 22.9 ms |

At 25,000 documents, warm-search p50 was 96.0 ms. Search p95 improved about
3.4× and cached-answer p95 about 29×. Cold reads and invalidated snapshots still
load the corpus; the cache retains up to eight views by default. Persisted
answer payloads contain the full authorized fingerprint list, and hit validation
still performs work proportional to its size. This is not an O(1) answer cache.
Raw data: [before](../company-brains-wave2/scale.json), [after](scale.json).

On 1,000 vectors with 20 queries, `k=10`, `ef_search=64`, and threshold 200:

| Allowed IDs | Approximate recall | Exact fallback recall |
| --- | ---: | ---: |
| 10 | 22/200 (11%) | 200/200 (100%) |
| 50 | 13/200 (6.5%) | 200/200 (100%) |
| 200 | 49/200 (24.5%) | 200/200 (100%) |
| 1,000 | 144/200 (72%) | 144/200 (72%; fallback not engaged) |

No unauthorized hits in any run. Small-set exact fallback cost roughly 1.3–1.7×
the approximate query time in this run. Full-corpus approximate recall is
unchanged. [Filtered retrieval results](filtered-recall.json).

## Live quality

The [corpus](quality-corpus.json) was reviewed and hashed before the 16 live
DeepSeek Flash answer requests. The coordinator corrected a label before this
run: an explicit statement that no global default exists supports a grounded
negative answer. No prompts or gold labels were changed after observing outputs.

- Expected answer/abstention disposition: **16/16**.
- Exact citation validation: **7/7 grounded responses**.
- Required abstentions: **9/9**, with no unnecessary abstentions.
- Lexical answer proxy: **6/7**. The sole miss correctly said “does not have a
  global default”; the rubric required the literal phrase “no global default”.
  The original score is preserved.
- Invalid responses: **0/16**; stale-content signals: **0/7** grounded responses.
- All seven grounded responses cited their controlling source. One also cited
  an informational summary to explain why it was superseded by the authoritative
  policy; additional citations are not inherently incorrect.

[Live results](live-quality.json), [source-authority audit](source-authority-audit.json).
This is a small synthetic development evaluation with lexical grading, not a
held-out production quality claim or a proof of semantic entailment. This wave
evaluated answering; extraction's prior-wave results remain unchanged.

## Validation and reproduction

**994 tests pass** (944 before this wave), Ruff lint/format pass, and Pyright
reports zero errors. Wheel and source distribution build successfully; the
installed wheel passes the durable lifecycle. Existing examples and all eight
first-wave scenarios pass. The deterministic durable lifecycle passes all ten
restart, cache, edit, permission, deletion, and projection checks.
The strict Sphinx build, algorithm inventory freshness check, and browser
sidebar checks also pass.

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m examples.company_brains.durable
.venv/bin/python -m benchmarks.company_brain_scale --sizes 1000 10000 25000 \
  --queries 20 --no-tracemalloc --output /tmp/brain-scale.json
.venv/bin/python -m benchmarks.company_brain_filtered_recall --size 1000 \
  --queries 20 --allowlist-sizes 10 50 200 1000 --exact-filter-threshold 200 \
  --output /tmp/brain-recall.json
.venv/bin/python -m examples.company_brains.durable.quality_wave3 --live \
  --output /tmp/brain-quality.json
```

Live evaluation requires `DEEPSEEK_API_KEY`; only synthetic questions and visible
source text are sent. All changes remain local and uncommitted.

## Remaining limits

The cache assumes writes go through the updated store methods. Raw SQL and old
writers do not maintain counters. Replacing/restoring the database requires new
brain instances. Snapshot consistency does not retract a response after a later
revocation. Authentication, deployment, backup operations, and distributed
concurrency remain host responsibilities.

The next useful work is a production retrieval adapter, bounded cache memory
under many users, and quality tests based on real host-approved company data.
Broader approximate recall remains a separate task; this wave fixes sparse
allowlists through an explicit exact fallback.
