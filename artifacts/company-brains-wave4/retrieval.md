> Agent handoff report. See [integrated results](README.md) for coordinator fixes, final measurements, and supported behavior.

# Company-brain wave 4: deterministic multi-start HNSW recall

## Change

`HNSWIndex.search` gained an explicit, opt-in `search_starts: int = 1` keyword.
The default and every existing call path are unchanged.

Semantics:

- `search_starts` must be a positive `int` (`bool` and non-integers are rejected
  with `ValueError`). `1` is the legacy single-start traversal.
- Start nodes are chosen deterministically from authorized IDs only. The first
  start is the canonical entry (highest level, smallest ID) and reproduces the
  legacy traversal exactly. Additional starts are the remaining authorized IDs
  in a deterministic `sha256` order, so each `search_starts` value uses a prefix
  of the same ordering and candidate sets stay nested as the count grows.
- Each start runs its own greedy descent followed by a best-first expansion
  bounded by `ef_search`, so total work grows with `search_starts`.
- Scored candidate dictionaries from every start are merged (scores are
  query-only) and ranked by `(-score, document_id)` before truncation to
  `limit`. Merging a superset of candidates can only add true top-k members, so
  top-k scores and exact-recall coverage are monotonically non-decreasing.
- Only authorized vectors are ever scored or returned. Empty and unknown-only
  allowlists return no hits.
- The opt-in `exact_filter_threshold` fallback is retained and takes precedence
  for small explicit allowlists; it is bit-identical to `DenseFlatIndex` for the
  same allowlist regardless of `search_starts`.
- The constructor, its parameters, and dependencies are unchanged.

## Method

`benchmarks/company_brain_multistart.py` reuses the wave-3 deterministic helpers
(`dense_vectors`, `_query_vectors`, defaults from
`benchmarks/company_brain_recall.py`, and `_sampled_allowlist` from
`benchmarks/company_brain_filtered_recall.py`). It therefore uses the same
1,000-vector corpus, the same 20 query vectors, and the same allowlist masks
(`random.Random(f"{seed}:{allowlist_size}:{position}")`) as wave 3.

The exact fallback stays disabled (`exact_filter_threshold=0`) so the measured
effect is multi-start graph search alone. `DenseFlatIndex` ground truth is
recomputed once per allowlist size and reused across starts; search time is
accumulated with `perf_counter` around the index calls only. Each run reports
recall (numerator/denominator), missed relevant hits, unauthorized hits, and
per-query latency.

Configuration: `size=1000`, `dimension=24`, `queries=20`, `k=10`, `m=8`,
`ef_search=64`, `seed=20240919`, `metric=cosine`, allowlists `200`/`1000`,
starts `1`/`4`/`8`, `exact_filter_threshold=0`. Recall denominator per size is
`20 * min(10, size) = 200`.

## Results

### Allowlist 200

| starts | recall | hits | missed | unauthorized | search (s) | ms/query | latency ratio |
| -----: | -----: | ---: | -----: | -----------: | ---------: | -------: | ------------: |
| 1      | 0.2450 | 49/200 | 151 | 0 | 0.0029 | 0.147 | 1.000 |
| 4      | 0.4800 | 96/200 | 104 | 0 | 0.0079 | 0.394 | 2.674 |
| 8      | 0.5650 | 113/200 | 87 | 0 | 0.0111 | 0.555 | 3.773 |

Gain over single start: **+0.2350** at 4 starts, **+0.3200** at 8 starts.

### Allowlist 1000 (full corpus)

| starts | recall | hits | missed | unauthorized | search (s) | ms/query | latency ratio |
| -----: | -----: | ---: | -----: | -----------: | ---------: | -------: | ------------: |
| 1      | 0.7200 | 144/200 | 56 | 0 | 0.0055 | 0.277 | 1.000 |
| 4      | 0.8900 | 178/200 | 22 | 0 | 0.0199 | 0.995 | 3.591 |
| 8      | 0.9000 | 180/200 | 20 | 0 | 0.0281 | 1.403 | 5.063 |

Gain over single start: **+0.1700** at 4 starts, **+0.1800** at 8 starts.

Totals: **zero unauthorized hits** across all six runs; recall is monotonic in
`search_starts` for both allowlists. HNSW build took 1.004 s; the six search
sweeps together took 0.075 s; ground-truth recomputation took 0.013 s. These are
local sequential measurements, not concurrent service load tests.

## Default-equivalence evidence

The `search_starts=1` rows reproduce wave 3's approximate (threshold `0`) recall
bit-for-bit, which shows both the wave-3 masks and the legacy single-start path
are preserved:

| Allowlist | Wave 3 approximate recall | Wave 4 `search_starts=1` | Unauthorized |
| --------: | ------------------------: | -----------------------: | -----------: |
| 200  | 49/200 (0.245) | 49/200 (0.245) | 0 |
| 1000 | 144/200 (0.720) | 144/200 (0.720) | 0 |

Source: wave-3 [`filtered-recall.json`](../company-brains-wave3/filtered-recall.json)
and wave-4 [`retrieval.json`](retrieval.json).

## Validation and reproduction

- `tests/test_brain4_retrieval.py` (31 tests) covers: signature/default,
  invalid-value rejection, exact default equivalence across `cosine`/`dot`/`l2`,
  monotonic top-k scores and recall coverage versus single start, strict recall
  improvement, determinism, limit handling, authorized-only start ordering and
  traversal, empty/unknown allowlists, unauthorized-ID exclusion, retained exact
  fallback, and the benchmark runner/CLI (masks, denominators, latency, zero
  unauthorized, determinism, validation).
- The wave-4 parallel integration test
  `test_single_start_selection_does_not_rescan_levels_quadratically` caught an
  early quadratic level scan in `_start_order`; the final implementation computes
  the top level once and short-circuits the single-start case.
- `ruff check` and `ruff format --check` pass on all three touched files.
- Related suites: `tests/test_brain4_retrieval.py`, `tests/test_brain3_recall.py`,
  `tests/test_index_families.py`, `tests/test_company_brain_retrieval_audit.py`,
  `tests/test_retrieval.py`, `tests/test_retrieval_algorithms.py` → **83 passed**.
- A full local run showed the only failures in other agents' in-flight files
  (cache/evidence validation and documentation); no retrieval test fails.

```bash
.venv/bin/python -m pytest tests/test_brain4_retrieval.py -q
.venv/bin/python -m benchmarks.company_brain_multistart --size 1000 \
  --queries 20 --allowlist-sizes 200 1000 --search-starts 1 4 8 \
  --output artifacts/company-brains-wave4/retrieval.json
```

## Remaining limits

Multi-start raises latency roughly 1:1 with the number of starts (about 2.7–5.1×
for 4–8 starts here) and its benefit flattens on the full-corpus allowlist
(0.890 → 0.900 from 4 to 8 starts). The start choices are deterministic and
graph-agnostic rather than learned, and the exact fallback remains the right tool
for small allowlists. These are synthetic Gaussian vectors with lexical-free
scoring, not a production relevance claim.
