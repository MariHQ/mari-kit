> Integration note: this is an agent report from the development run. See [the integrated results](README.md) for final fixes, measurements, and verification.

# Scale benchmark review (wave 2)

Reviewer: scale reviewer. Owner of this file and
`tests/test_brain2_benchmark_review.py`. No builder file was edited, no git
state changed, no full suite run.

## What was reviewed

| File | Role |
| --- | --- |
| `benchmarks/company_brain_scale.py` | scale builder's benchmark (primary target) |
| `examples/company_brains/durable/engine.py` | actual query/answer path the benchmark should reflect |
| `examples/company_brains/durable/store.py` | durable read/write path |
| `src/mari_kit/retrieval/indexes.py` | `BM25Index` / `RevisionBM25Index` asymptotics |
| `benchmarks/company_brain_recall.py` | sibling benchmark, cross-checked for the same hazards |

The benchmark exists (753 lines) and the durable store/engine are importable,
so this is a real review, not a placeholder.

## Commands and measurements

All commands used `.venv/bin/python` with `PYTHONPATH` set to the repo root;
timings are on one macOS machine, single run, and are illustrative not
statistical.

```bash
# benchmark, small end-to-end run, engine probe on
.venv/bin/python benchmarks/company_brain_scale.py --sizes 200 --queries 20 \
  --output <tmp>/scale200.json

# independent lexical-index asymptotics (n documents, 40-token bodies)
.venv/bin/python <tmp>/scale_probe.py
.venv/bin/python <tmp>/scale_probe2.py
.venv/bin/python <tmp>/scale_probe3.py
.venv/bin/python <tmp>/scale_probe4.py
```

Observed at size 200 (`scale200.json`):

```
warm_lexical_query   count=20 p50=0.0140s p95=0.1737s
acl_filtered_query   count=20 p50=0.0443s p95=0.1644s
cold_index_build     count=1  p50=p95=0.0122s
batch_edit_index_update count=1 p50=p95=0.0420s
engine_search        count=1  p50=p95=0.3412s   (24x warm_lexical_query)
engine_answer        count=1  p50=p95=0.8093s
counts: authorized_refs=175 total_refs=200
acl_filtered_query rss_before == rss_after == 56049664
database_bytes=4096
```

Independent `BM25Index` probes (`indexes.py`):

```
search scores every authorized document regardless of limit:
  allowed=4000 limit=5 -> 4000 docs scored; allowed=7 -> 7 docs scored
search cost tracks authorized count A, not output limit:
  A=0 0.14ms | A=100 0.97ms | A=4000 19.9ms
single-document with_deltas rebuilds the whole snapshot:
  n=500 20.8ms | n=1000 27.0ms | n=2000 194.9ms | n=4000 337.8ms
```

Store update probe (`store.py`), one edit / one delete:

```
n=250  full=0.219s 1edit=8.5ms   1delete=4.4ms   access_snapshot=3.7ms
n=500  full=0.297s 1edit=16.1ms  1delete=11.6ms  access_snapshot=7.4ms
n=1000 full=0.760s 1edit=253.8ms 1delete=9.9ms   access_snapshot=12.8ms
n=2000 full=0.896s 1edit=248.3ms 1delete=170.3ms access_snapshot=199.1ms
```

Sibling `HNSWIndex` build is quadratic and must never be run at the contract's
large sizes (`--sizes 1000 10000 25000`): 250 -> 1.38s, 500 -> 4.44s,
1000 -> 16.7s, 2000 -> 80.1s.

## Findings: misleading metrics and exact fixes

### 1. `warm_lexical_query` is not a warm engine query (high)

`benchmarks/company_brain_scale.py:478-487` builds one `RevisionBM25Index`
over the durable projection and times `index.search`. The real engine
(`engine.py:142-149`) reads `store.access_snapshot` and constructs a brand-new
`RevisionBM25Index` on **every** `search` call, and `_default_generate`
(`engine.py:307-311`) does the same on every uncached answer. The engine has no
warm index path. At size 200 the "warm" reference query is `0.0140s` while the
real `engine_search` is `0.3412s` (24x). A reader will take `warm_lexical_query`
as the engine's steady-state query cost; it is not.

Fix:
- Rename the phase to `reference_index_query` (or `prebuilt_index_query`).
- Add `engine_search_first` (cold) and `engine_search_repeated` with at least
  20 samples, and `engine_answer_cold` / `engine_answer_cached`, so the engine's
  cold and cache-hit paths are both real and separately reported.
- State in `reference_index_note` that the durable engine rebuilds the index and
  re-reads the full snapshot per request, so its query is O(corpus) and never
  warm. (The actual fix of caching belongs to the engine owner; the benchmark's
  job is to disclose it.)

### 2. Single-sample phases are reported as p50/p95 (high)

`Recorder.to_dict` (`benchmarks/company_brain_scale.py:357`) uses
`samples or [self.wall_seconds]`, so every phase that never calls `.sample()`
is summarized with `count=1`, and the nearest-rank `p95` equals that one value.
This affects `cold_index_build`, `batch_edit_index_update`,
`batch_delete_index_update`, `engine_search`, and `engine_answer`. It is not a
p95 at all.

Fix:
- Repeat the engine probes (see finding 1) so they carry >= 20 samples.
- For genuinely one-shot phases, set `"latency_kind": "single_shot"` and omit
  `p50_seconds`/`p95_seconds`, or add `"p95_valid": false`. Include `count` in
  every summary (already present) and never present a one-sample value as a
  percentile.

### 3. Per-query hidden rebuild is not surfaced as a cost (high)

The benchmark only discloses the `with_deltas` rebuild
(`reference_index_note`, line 670). The larger hidden rebuild is
`RevisionBM25Index(...)` inside `engine.search` and `engine.answer`. The
`engine_probe` (lines 567-593) times the engine once, so the rebuild is buried
inside an undifferentiated `engine_search` number.

Fix: decompose the engine probe into named phases:
`store_access_snapshot` (all N live docs), `authorized_filter` (N -> A),
`engine_index_build` (A docs), `engine_index_search` (scores all A), and
`engine_answer_parse`. Report `snapshot_documents=N` beside `authorized_refs=A`
so the O(N) read and O(A) build are visible. Independent probe confirms
`RevisionBM25Index` search scores all A documents regardless of `limit`.

### 4. RSS numbers are process high-water marks, not per-phase/per-size deltas (high)

`process_rss_bytes` (`benchmarks/company_brain_scale.py:309-317`) returns
`ru_maxrss`, which is the maximum RSS the process has ever held. `Recorder`
records `rss_before` and `rss_after` from the same monotonic value, so the
implied delta is zero once any earlier phase peaked. Observed: at size 200
`acl_filtered_query`, `batch_edit_commit`, and `engine_answer` all report
`rss_before == rss_after`; the top-level `process_rss_peak_bytes=59736064` is
the same global value for every requested size.

Fix:
- Report `process_rss_peak_bytes` (ru_maxrss) exactly once, clearly labeled as a
  process-lifetime high-water mark, and delete the per-phase `before`/`after`
  fields (or rename them `*_peak_bytes` and document that they are not deltas).
- To get real per-phase/per-size RSS, either sample current RSS
  (`/proc/self/statm` on Linux, `ps -o rss=` elsewhere) at phase boundaries, or
  run each size in a fresh subprocess and read `RUSAGE_CHILDREN` after `wait`.
  Keep tracemalloc separately as the Python-allocation view; SQLite/numpy
  allocations are invisible to it.

### 5. `database_bytes` understates the durable footprint (medium)

`database.stat().st_size` (`line 595`) is read while the store uses WAL
(`store.py:203`, `PRAGMA journal_mode = WAL`). The size-200 run reported
`database_bytes=4096` (one page) although the WAL held the corpus; after the
process exits and the WAL checkpoints, the file is ~700 KB. The metric can be
off by two orders of magnitude.

Fix: `PRAGMA wal_checkpoint(TRUNCATE)` before measuring, or report the sum of
`database`, `database-wal`, and `database-shm` sizes (with WAL present or not).

### 6. Authorization cardinality is a single dense point (medium)

`counts.authorized_refs=175/200` is 87.5% of the corpus. The contract asks to
separate ACL filtering; one dense point cannot. `BM25Index.search` iterates the
full N-token dictionary and scores every authorized doc, so filtering cost is
governed by both N and A. The benchmark also filters a **prebuilt full index**
via `allowed_refs` (line 503), whereas the engine filters documents first and
builds the index on the authorized subset — two different cost profiles.

Fix: sweep at least three cardinalities (anonymous user: open docs only;
narrow team; all teams) using the engine's own policy helper, and report
`authorized_refs`/`total_refs` per point. Add an engine ACL query measured
through `brain.search(..., user_id=<restricted>)` so the filtered-build path is
captured, not just the prebuilt-index filter.

### 7. p95 sample adequacy (medium)

`percentile` is nearest-rank (`lines 279-287`), so p95 of 5 samples is the
maximum and p95 of 1 sample is that sample. `commit` and the batch phases use
`count=5` (one sample per source, not per document); the engine and index-update
phases use `count=1`. The default `--queries 20` is the only phase near a
stable p95.

Fix: require `count >= 20` for any emitted p95, or emit `p95_valid: bool` with
the count; keep the default query count at 20 but recommend 100 for the
non-CI run. `commit` can sample per document/plan deterministically rather than
per source.

### 8. `commit` phase excludes planning and rewrites the full manifest (low/medium)

`_plan` (`lines 379-397`) runs `store.state` + `plan_sync` outside the timed
block, so `commit` is not end-to-end sync. Also `store._write_state`
(`store.py:428-439`) encodes the entire `SyncState`, whose `manifest` contains
every live document, on every incremental update; a single-document edit is
therefore O(N) in write bytes even though `_write_documents` is incremental.
The measured edit time grows with N (8.5ms -> ~250ms), consistent with this.

Fix: clarify whether `commit` is store-only or plan+store; if plan+store,
include it. Report `sync_state_bytes`/manifest entries per update so the O(N)
write amplification is explicit, and do not describe the edit phase as
"incremental update" without that qualifier.

### 9. Query relevance is exercised but not reported (low/medium)

The generated queries are non-degenerate: an independent check over
`build_documents(200)` / `build_queries(20)` shows all 20 queries score at
least one positive `BM25Index` hit, so the corpus is not the all-zero-score
trap. However the report returns no per-query relevance signal (positive-hit
rate, whether the top score exceeds zero, or hit counts), so a reader cannot
tell whether a size's index is returning real matches or merely all-zero
documents. Fix: add `queries_with_positive_hits` and
`mean_positive_hits_per_query` counts per size, computed from the same
`RevisionBM25Index` already built. (Recall against ground truth is out of scope
here; `company_brain_recall.py` covers that.)

### 10. `run()` failure mode does not match its docstring (low)

The module docstring says the CLI "exits with a clear message when the durable
store module is still absent", but `run()` raises `RuntimeError` (`line 636`)
and `main()` does not catch it, producing a traceback. Fix: catch in `main`,
print the message, `return 1`.

## Attribution: benchmark defects vs host responsibilities

- Findings 1-3 and 7 are benchmark-reporting defects. The underlying behavior
  (per-request rebuild, O(N) snapshot, all-authorized scoring) is a legitimate
  host/application implementation choice for a reference app; the benchmark must
  measure and label it, not imply a warm sublinear engine.
- Findings 4-6 and 8 are measurement defects (RSS semantics, WAL accounting,
  cardinality coverage, manifest write amplification). The host store code is
  doing what it says; the metrics understate or overstate it.
- No Mari library defect is claimed. `BM25Index.with_deltas` is documented as a
  full rebuild; the benchmark's `reference_index_note` already says so.

## Limitations

- Single machine, single run per size; the store numbers above are one sample
  (e.g. the 1000/2000 edit jump is within run-to-run noise) and are used only to
  show growth trend, not as calibrated constants.
- I did not run the contract's large sizes (`1000 10000 25000`) and did not run
  the full test suite, per instructions.
- The `company_brain_recall.py` HNSW probe was measured out of process; it is a
  sibling file, not owned here, but the quadratic build is a real scheduling
  hazard for any large-size invocation.
- This review covers methodology and measured asymptotics; it does not certify
  the correctness of the durable engine, store, or quality evaluator, which have
  their own reviewers.

## Functional metric validation tests

`tests/test_brain2_benchmark_review.py` (owned) re-derives the benchmark's
reported metrics independently: nearest-rank percentile correctness,
latency-summary consistency, phase sample counts matching recorded samples,
authorized-ref count recomputed from the public policy helper, query-relevance
positivity, and `with_deltas` rebuild-equivalence. These are lightweight and
assert no latency thresholds.
