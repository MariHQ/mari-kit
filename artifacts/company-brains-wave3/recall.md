# Company-brain wave 3: opt-in exact fallback for filtered HNSW recall

## Change

`HNSWIndex.search` gained an explicit, opt-in `exact_filter_threshold: int = 0`
keyword. Defaults and all existing call paths are unchanged.

Semantics:

- `exact_filter_threshold` must be a non-negative `int` (`bool` and non-integers
  are rejected with `ValueError`); `0` disables the feature.
- The fallback engages only when an allowlist is explicitly supplied
  (`allowed_document_ids is not None`) and the effective allowed count, i.e. the
  intersection of the allowlist with the indexed IDs, is `<= threshold`.
- When engaged, search delegates to `DenseFlatIndex.search(query, ...)` with the
  already-intersected allowlist, so it scores and returns only authorized
  vectors and is bit-identical to exact flat search for the same allowlist.
- Unknown allowlist IDs are never scored and never inflate the effective count;
  an unknown-only or empty allowlist yields no hits.
- The `DenseFlatIndex` path supports `cosine`, `dot`, and `l2` identically.

## Method

`benchmarks/company_brain_filtered_recall.py` reuses the wave-2 deterministic
helpers (`dense_vectors`, `_query_vectors`, defaults) from
`benchmarks/company_brain_recall.py` and reproduces the same allowlist masks
(`random.Random(f"{seed}:{allowlist_size}:{position}")`). For each allowlist
size it runs two sweeps over the identical corpus and identical query masks:

- **approximate**: `HNSWIndex.search(..., exact_filter_threshold=0)`
- **fallback**: `HNSWIndex.search(..., exact_filter_threshold=8)`

Recall is `numerator / denominator` where the denominator is the exact flat
top-k size per query (`queries * min(k, allowlist_size)` over the sweep), and
`unauthorized_hits` counts returned IDs outside the allowlist. Search time is
the accumulated `perf_counter` deltas of the index calls only; exact ground
truth is timed separately so the two sweeps stay comparable. A test asserts the
approximate totals equal wave-2 `filtered_dense_recall` totals, proving the
masks match.

## Results

Configuration: `dimension=24`, `queries=32`, `k=10`, `m=8`, `ef_search=64`,
`seed=20240919`, `exact_filter_threshold=8`. Recall denominator per size =
`32 * min(10, size)`; the seven sizes total 1440.

### Corpus size 240

| metric | allowlist | engaged | approx recall | fallback recall | gain | approx ms | fallback ms | time ratio | unauth |
| ------ | --------: | :-----: | ------------: | --------------: | ---: | --------: | ----------: | ---------: | -----: |
| cosine | 1         | yes     | 1.0000        | 1.0000          | 0.000 | 0.663 | 0.749 | 1.13 | 0 |
| cosine | 2         | yes     | 0.5000        | 1.0000          | 0.500 | 0.555 | 0.753 | 1.36 | 0 |
| cosine | 4         | yes     | 0.2656        | 1.0000          | 0.734 | 0.586 | 0.815 | 1.39 | 0 |
| cosine | 8         | yes     | 0.1445        | 1.0000          | 0.855 | 0.664 | 0.911 | 1.37 | 0 |
| cosine | 16        | no      | 0.1156        | 0.1156          | 0.000 | 0.757 | 0.754 | 1.00 | 0 |
| cosine | 32        | no      | 0.1844        | 0.1844          | 0.000 | 1.011 | 1.032 | 1.02 | 0 |
| cosine | 64        | no      | 0.6062        | 0.6062          | 0.000 | 3.041 | 2.993 | 0.98 | 0 |
| dot    | 1         | yes     | 1.0000        | 1.0000          | 0.000 | 0.542 | 0.641 | 1.18 | 0 |
| dot    | 2         | yes     | 0.5000        | 1.0000          | 0.500 | 0.504 | 0.652 | 1.29 | 0 |
| dot    | 4         | yes     | 0.2656        | 1.0000          | 0.734 | 0.489 | 0.730 | 1.49 | 0 |
| dot    | 8         | yes     | 0.1602        | 1.0000          | 0.840 | 0.534 | 0.757 | 1.42 | 0 |
| dot    | 16        | no      | 0.1031        | 0.1031          | 0.000 | 0.629 | 0.618 | 0.98 | 0 |
| dot    | 32        | no      | 0.1781        | 0.1781          | 0.000 | 0.928 | 0.878 | 0.95 | 0 |
| dot    | 64        | no      | 0.6031        | 0.6031          | 0.000 | 2.871 | 2.638 | 0.92 | 0 |
| l2     | 1         | yes     | 1.0000        | 1.0000          | 0.000 | 0.557 | 0.699 | 1.26 | 0 |
| l2     | 2         | yes     | 0.5000        | 1.0000          | 0.500 | 0.487 | 0.729 | 1.50 | 0 |
| l2     | 4         | yes     | 0.2656        | 1.0000          | 0.734 | 0.510 | 0.781 | 1.53 | 0 |
| l2     | 8         | yes     | 0.1445        | 1.0000          | 0.855 | 0.601 | 0.829 | 1.38 | 0 |
| l2     | 16        | no      | 0.1250        | 0.1250          | 0.000 | 0.790 | 0.773 | 0.98 | 0 |
| l2     | 32        | no      | 0.2281        | 0.2281          | 0.000 | 1.186 | 1.132 | 0.95 | 0 |
| l2     | 64        | no      | 0.4719        | 0.4719          | 0.000 | 2.653 | 2.675 | 1.01 | 0 |

Sweep totals (all sizes): cosine approximate `0.2951` -> fallback `0.5347`; dot
`0.2931` -> `0.5299`; l2 `0.2771` -> `0.5167`. Unauthorized hits: `0` in every
row and in both sweeps. HNSW build: cosine `0.0548 s`, dot `0.0534 s`,
l2 `0.1145 s`.

### Corpus size 1000 (cosine)

| allowlist | engaged | approx recall | fallback recall | gain | approx ms | fallback ms | time ratio | unauth |
| --------: | :-----: | ------------: | --------------: | ---: | --------: | ----------: | ---------: | -----: |
| 1  | yes | 1.0000 | 1.0000 | 0.000 | 1.679 | 2.311 | 1.38 | 0 |
| 2  | yes | 0.5156 | 1.0000 | 0.484 | 1.549 | 2.425 | 1.57 | 0 |
| 4  | yes | 0.2578 | 1.0000 | 0.742 | 1.619 | 2.589 | 1.60 | 0 |
| 8  | yes | 0.1328 | 1.0000 | 0.867 | 1.656 | 2.552 | 1.54 | 0 |
| 16 | no  | 0.0625 | 0.0625 | 0.000 | 1.686 | 1.693 | 1.00 | 0 |
| 32 | no  | 0.0719 | 0.0719 | 0.000 | 1.845 | 1.834 | 0.99 | 0 |
| 64 | no  | 0.0500 | 0.0500 | 0.000 | 2.147 | 2.119 | 0.99 | 0 |

Sweep totals: `0.1326` -> `0.3743`; unauthorized hits `0`; HNSW build `0.9783 s`.

### Reading

For sparse allowlists the approximate HNSW path is genuinely poor: with one to
eight authorized documents the deterministic corpus recovers only 13-50% of the
exact top-k. The fallback recovers 100% for every engaged row at roughly
1.1-1.6x the approximate query time (sub-millisecond absolute cost at size 240,
low milliseconds at size 1000). Sizes above the threshold are untouched
(`gain = 0.0`, ratio ~1.0), and no run ever returned an unauthorized ID.

## Tests

`tests/test_brain3_recall.py` (17 tests) pins:

- bit-identical equality with `DenseFlatIndex` for cosine, dot, and l2;
- deterministic repeated fallback results;
- default and `exact_filter_threshold=0` compatibility, and no fallback without
  an explicit allowlist;
- effective-count semantics via a recording flat index (unknown IDs excluded
  before comparison, no delegation when the effective count exceeds threshold);
- unknown-only and empty allowlists return no hits, and unauthorized IDs are
  never returned or scored;
- limit/tie-break ordering preserved;
- threshold validation (`-1`, `1.5`, `True`, `"2"`, `None` rejected);
- benchmark recall denominators, exact engaged recall, per-condition timing,
  determinism after stripping timing, mask parity with wave-2 helpers, CLI JSON
  output, and input validation.

## Reproduce

```shell
python -m benchmarks.company_brain_filtered_recall \
  --size 240 --exact-filter-threshold 8 \
  --output /tmp/recall.json
python -m benchmarks.company_brain_filtered_recall --size 1000 --metric cosine
.venv/bin/python -m pytest tests/test_brain3_recall.py -q
```
