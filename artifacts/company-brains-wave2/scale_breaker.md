> Integration note: this is an agent report from the development run. See [the integrated results](README.md) for final fixes, measurements, and verification.

# scale_breaker report — deterministic filtered-retrieval recall

Owner: scale_breaker (wave 2). Scope: recall experiments only; no core edits.

## Files

| File | Role |
| --- | --- |
| `benchmarks/company_brain_recall.py` | Deterministic recall runner (dense filtered + BM25 lifecycle) with `--size`/`--output` CLI |
| `tests/test_brain2_recall.py` | 10 behavioral tests pinning denominators, allowlist isolation, edit/delete correctness, rebuild equivalence, CLI output |
| `artifacts/company-brains-wave2/scale_breaker.md` | This report |

No other files were modified. `src/mari_kit/retrieval/indexes.py` was already
dirty in the working tree when this task started (`git diff`: +72/-2, owned by
other agents; HNSW/BM25 sections untouched by those edits). Pinned for
reproducibility: `sha256=319d86645442b14d8aeb6bf4daf237f87f5c31feb64cac0f907baaafd35438ba`.

## Commands

```shell
.venv/bin/ruff check benchmarks/company_brain_recall.py tests/test_brain2_recall.py
.venv/bin/python -m pytest tests/test_brain2_recall.py -q          # 10 passed
.venv/bin/python benchmarks/company_brain_recall.py \
  --size 1000 --queries 40 --k 10 --seed 20240919 \
  --allowlist-sizes 1 2 4 8 16 32 64 \
  --output /tmp/recall_report.json
# wall time: 1.64 s, CPU 99% (idle host)
```

The runner also accepts `--dimension`, `--m`, `--ef-search`, and prints JSON to
stdout when `--output` is omitted. Two runs with the same seed are byte-equal
after stripping the wall-clock `timing_seconds` blocks (verified).

## Dense filtered recall — exact `DenseFlatIndex` vs `HNSWIndex`

Corpus 1000 docs, dim 24, cosine, m=8, ef_search=64, 40 queries, k=10.
Ground truth is the exact restricted top-k. Denominator is
`min(k, allowlist_size)` per query.

| Allowlist size | Recall numerator | Recall denominator | Recall | Unauthorized hits |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 40 | 40 | 1.0000 | 0 |
| 2 | 41 | 80 | 0.5125 | 0 |
| 4 | 43 | 160 | 0.2687 | 0 |
| 8 | 42 | 320 | 0.1313 | 0 |
| 16 | 26 | 400 | 0.0650 | 0 |
| 32 | 27 | 400 | 0.0675 | 0 |
| 64 | 20 | 400 | 0.0500 | 0 |
| **Total** | **239** | **1800** | **0.1328** | **0** |

`ef_search` sensitivity (same run):

| Allowlist size | ef=10 | ef=64 | ef=256 |
| ---: | ---: | ---: | ---: |
| 4 (sparse) | 0.2687 | 0.2687 | 0.2687 |
| 1000 (full) | 0.3950 | 0.7025 | 0.9325 |

Key facts:

* **Authorization never leaks.** Unauthorized hits were 0 in every
  configuration: filtering happens before scoring/return, so the sparse
  allowlist is a recall problem, not a confidentiality problem.
* **Sparse filtered recall collapses.** HNSW returns ~1 authorized document per
  query for allowlists up to 16 even though exact search returns `min(k, size)`.
  Raising `ef_search` from 10 to 256 changes nothing for the sparse allowlist.
* **Full-corpus recall behaves as an approximate index should**: full allowlist
  improves 0.395 → 0.703 → 0.933 with `ef_search`, confirming the mechanism is
  the allowlist restriction, not a broken approximate search.

## BM25 known-relevant docs before/after edits and deletions

Corpus 1000 lexical docs, each with one unique marker token. One doc is edited
(marker moved), one deleted, one inserted, all through
`BM25Index.with_deltas` (revision-checked).

| State | Recall numerator | Recall denominator | Recall | Unexpected positives |
| --- | ---: | ---: | ---: | ---: |
| Before edits | 2 | 2 | 1.0 | 0 |
| After edits/deletes | 2 | 2 | 1.0 | 0 |

* Edited doc: old marker has no positive hit afterwards; new marker resolves to
  the edited doc.
* Deleted doc: absent from full rankings (`deleted_document_visible=false`), so
  no stale/ghost hits.
* Restricted query (allowlist excludes the edited doc): positive hits `[]`,
  unauthorized `0`.

### Rebuild equivalence (proof)

For the edit+delete+insert batches, the incrementally updated snapshot
(`base.with_deltas(first).with_deltas(second)`) and a single combined batch were
compared against a freshly constructed `BM25Index` over the final documents:

* `documents_equal=true`, `revisions_equal=true`
* `rankings_equal=true` across 16 probes (old/new markers, shared terms, all
  filler terms); `mismatches=[]`

## Defects vs host responsibilities

1. **HNSW filtered-search recall collapse (library behavior, host decides
   exposure).** Root cause: restricted search chooses one allowed entry and only
   walks level-0 edges whose endpoints are also in the allowlist. Edges were
   built over the full corpus, so a sparse random allowlist induces a nearly
   disconnected subgraph; the frontier dies after ~1 node. `ef_search` cannot
   help because it only bounds `visited`, not reachability.
   *Host responsibility:* the store/engine chooses between exact and
   approximate filtered retrieval and owns the resulting recall. It must not
   assume that `HNSWIndex` preserves recall under ACL allowlists. The library
   currently provides no signal (no returned-count diagnostic, no error).
2. **Silent under-return in the engine path.** Because the result is a valid
   tuple with 0 unauthorized hits, an engine can serve
   `insufficient_evidence` while authorized evidence exists. That is an
   availability defect invisible to an unauthorized-hit check alone.
3. **Inconsistent delete semantics across snapshots.** `BM25Index.with_deltas`
   silently ignores a DELETE for an absent `item_id`
   (`documents.pop(..., None)`), while `ArtifactBM25Index`/`RevisionBM25Index`
   raise `ValueError` for the same case. A host that relies on the lexical
   projection cannot distinguish "already gone" from "ID typo". Minor, but it
   weakens the rebuild-equivalence contract.

## Exact recommended fixes

* **Host (store/engine owner):** select retrieval by allowlist density. For
  `len(allowed) <= threshold` (sparse), call `DenseFlatIndex.search(..., allowed_document_ids=...)`
  or the lexical index, both of which are exact under filtering. Reserve
  `HNSWIndex` for dense/full-corpus retrieval or per-ACL sub-indexes.
* **Library (optional, if HNSW must serve sparse allowlists):** in
  `HNSWIndex.search`, after the BFS exhausts the frontier with fewer than
  `limit` results, complete the result set by an exact scan of the remaining
  allowed ids. Sparse allowlists are cheap to complete exactly; equivalence with
  `DenseFlatIndex` is restored without changing the dense path. Alternatively
  build and cache per-allowlist sub-indexes.
* **Observability:** return (or expose) the number of authorized candidates
  visited so the host can detect `len(hits) < limit` under filtering.
* **Delete consistency:** make `BM25Index.with_deltas` reject a DELETE for an
  absent `item_id` (or document the no-op explicitly) to match the ref-keyed
  adapters.

## Limitations

* Recall is measured on synthetic Gaussian vectors and synthetic marker text,
  not production embeddings; magnitudes are indicative, the sparse-allowlist
  mechanism is the transferable finding.
* Timing is wall-clock and host-contended. Under concurrent agent load the same
  1000-doc HNSW build measured 18.5 s (13% CPU) vs 1.0 s (99% CPU) idle. Recall
  metrics are deterministic and are the evidence here; timing is not.
* Only `DenseFlatIndex` vs `HNSWIndex` is covered. IVF-PQ and hybrid fusion are
  out of scope and unmeasured.
* The durable store/engine (`examples/company_brains/durable`) were owned by
  other agents and not imported; no end-to-end integration claim is made.

## Test coverage

`tests/test_brain2_recall.py` (10 passing): denominator arithmetic, always-zero
unauthorized hits (including the ef sweep), singleton-allowlist exactness,
adversarial disallowed-neighbor filtering, before/after marker relevance,
deleted-doc invisibility, restricted-query isolation, revision-mismatch
rejection with base immutability, seed determinism, CLI `--output` JSON, and
tiny-corpus rejection.
