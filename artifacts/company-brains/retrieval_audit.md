> Integration note: this is the original agent report. Findings and intermediate failures below are historical; see [the integrated report](README.md) for final fixes and verification.

# Company Brain Retrieval Audit — Revision-Aware Authorization Filtering

Owner: audit agent (exclusive ownership of `src/mari_kit/retrieval/indexes.py`,
`tests/test_company_brain_retrieval_audit.py`, this report).

Scope: the dependency-light reference indexes in
`src/mari_kit/retrieval/indexes.py`, with emphasis on the revision-aware,
authorization-filtered paths (`ArtifactBM25Index`, `RevisionBM25Index`,
`BM25Index.with_deltas`) and the allowlist/empty-allowlist behavior of the
vector indexes.

## Summary

| # | Finding | Status |
|---|---------|--------|
| 1 | `ArtifactBM25Index` / `RevisionBM25Index` silently break their own structural tie-break once a corpus reaches ten units | **Fixed** with regression tests |
| 2 | `HNSWIndex` allowlist search can omit allowed documents whose graph neighborhood is entirely disallowed | **Reported, not fixed** (documented pre-filter design; no disallowed leakage) |
| 3 | `BM25Index.search` returns zero-score non-matching documents to fill `limit` | Observation only, not a bug |
| 4 | `RevisionBM25Index` has no update/delete path, while a concurrent test expects `RevisionIndexDelta` | **Reported, not fixed** (new public API; interface file not owned) |

No authorization leak was found: every filtered index returned only refs from
the caller's allowlist, and an empty allowlist always returned no hits.

## Finding 1 — ref-keyed tie-break collapses at ten units (FIXED)

### Symptom

Both ref-keyed adapters canonicalize their units once by structural key:

```python
ordered = tuple(sorted(units, key=lambda ref: ref.key))
self._refs = {str(index): ref for index, ref in enumerate(ordered)}
```

They then delegate ranking to `BM25Index`, which breaks score ties with a plain
string comparison of `document_id`. With synthetic IDs `str(0)…str(N-1)` the
string order diverges from the structural order at `N >= 11`, because `"10"`
sorts before `"2"`. Ties are common (identical chunk text, or zero-score
non-matches), and `limit` truncation then returns a *different set* of units
than the adapter's own canonical order.

Pre-fix reproduction (12 identically-scored units, refs `policy00…policy11`):

```
artifact limit 3: ['policy00', 'policy01', 'policy10']
artifact limit 5: ['policy00', 'policy01', 'policy10', 'policy11', 'policy02']
revision key ord: ['policy00', 'policy01', 'policy02']
```

Adding lower-key units could therefore evict a higher-key unit from the top
`limit`. The ranking was deterministic run-to-run, but inconsistent with the
`ref.key` order the adapter itself establishes.

### Fix

Added a module-level `_position_key(index, count)` that zero-pads the numeric
position to the width required by `count`, so string order equals numeric order
for every unit, and used it in both adapters
(`src/mari_kit/retrieval/indexes.py`). Unchanged for `< 10` units.

```python
def _position_key(index: int, count: int) -> str:
    return str(index).zfill(len(str(max(count - 1, 0))))
```

Regression coverage:
`tests/test_company_brain_retrieval_audit.py::test_ref_keyed_tie_break_follows_structural_order_past_ten_units`
and `...::test_ref_keyed_ranking_is_independent_of_construction_order`.

Pre-fix/post-fix proof:

```
# pre-fix (helper temporarily changed to `str(index)`)
FAILED tests/test_company_brain_retrieval_audit.py::test_ref_keyed_tie_break_follows_structural_order_past_ten_units
  At index 2 diff: 'policy10' != 'policy02'
# post-fix
1 passed / 13 passed for the whole audit module
```

## Finding 2 — HNSW allowlist traversal can miss allowed documents (REPORTED)

`HNSWIndex.search` restricts traversal itself to the allowlist: it selects the
descent entry only from allowed nodes and skips disallowed neighbors at every
level. Because construction neighbors are chosen over the **whole** corpus, an
allowed node's edges can point exclusively at disallowed nodes, and an allowed
component can be reachable only through disallowed hops. The frontier then
empties with allowed documents still unvisited.

Reproduction (50 docs, `m=8`, `ef_search=50` = corpus size, allowlist of 5):

```
flat  allowed: ['v2', 'v1', 'v4', 'v3', 'v0']
hnsw  allowed: ['v4', 'v0']          # 2 of 5 allowed docs
allowed reachable from chosen entry: {'v0', 'v4'}
```

This is *not* an authorization violation — no disallowed id is ever returned.
It is a recall/liveness limitation of the pre-filter traversal. It is also
consistent with the documented design (`IMPLEMENTATION.md`: "Approximate
retrieval filters permitted rows before proxy scoring") and with the reported
approximate recall of the index family. I did not change it: making filtered
search traverse disallowed nodes as routing hops, or brute-forcing the
allowlist, would change a documented design property and is beyond a minimal
bug fix. Recorded here so a maintainer can decide. Authorization safety itself
is covered by
`test_hnsw_authorization_never_returns_disallowed_ids`.

## Finding 3 — BM25 returns zero-score non-matches (OBSERVATION)

`BM25Index.search` emits one hit per indexed document and lets unmatched terms
contribute `0.0`, so a query returns non-matching documents (score `0.0`) until
`limit` is reached. This is why, for example, an allowed ref whose text lacks
the query term still appears. It is a ranking-policy choice, not a defect, and
is left unchanged. Tests were written to avoid relying on it.

## Finding 4 — no revision delta path for `RevisionBM25Index` (REPORTED)

`ArtifactBM25Index` supports `with_deltas(ArtifactIndexDelta(...))` (update,
replacement with `previous_ref` staleness check, delete), but
`RevisionBM25Index` exposes only `search`/`explain`. A concurrent agent created
`tests/test_revision_index_updates.py` importing `RevisionIndexDelta` from
`mari_kit.retrieval`, which does not exist and currently breaks collection of
the full suite. I did not add this API: it is a new feature rather than a proven
bug in existing behavior, it is not promised by the docs or the API inventory,
and exporting it would require editing `src/mari_kit/retrieval/__init__.py`,
which this task does not own. Flagged for the maintainer.

## Behaviors verified with no bug found

- **Empty allowlists** return `()` without error for `DenseFlatIndex`,
  `SparseVectorIndex`, `BM25Index`, `HNSWIndex`, `IVFPQIndex`,
  `ArtifactBM25Index`, and `RevisionBM25Index`.
- **Authorization filtering** restricts results to the allowlist; unknown refs
  are ignored; refs differing only by revision, scope, or unit never authorize
  one another. A randomized check confirmed exact indexes behave as a true
  post-filter (filtered result equals unfiltered result intersected with the
  allowlist) over 200 seeds.
- **Stale revisions**: `BM25Index` raises on `expected_revision` mismatch;
  `ArtifactBM25Index` raises when `previous_ref` is absent. After an update, the
  superseded revision is unreachable and its allowlist yields nothing.
- **Updates and deletion** are immutable (the source snapshot is unchanged), and
  deleting the last unit yields an empty, searchable index.
- **Deterministic results**: rankings are identical across repeated calls and
  across shuffled construction order; scope partitions do not mix.

## Commands and results

Run from `/Users/henneberger/mari-kit` with `.venv/bin/python`.

```
$ .venv/bin/python -m pytest tests/test_company_brain_retrieval_audit.py \
    tests/test_index_families.py tests/test_composition_primitives.py \
    tests/test_algorithm_composition_round2.py tests/test_retrieval_algorithms.py \
    tests/test_retrieval.py tests/test_dependency_updates.py -q
82 passed in 0.26s

$ .venv/bin/python -m pytest tests -q --ignore=tests/test_revision_index_updates.py
688 passed in 2.56s

$ .venv/bin/python -m pytest tests -q
ERROR tests/test_revision_index_updates.py
E   ImportError: cannot import name 'RevisionIndexDelta' from 'mari_kit.retrieval'
1 error during collection   # concurrent agent's file, not owned here

$ .venv/bin/python -m ruff check src/mari_kit/retrieval/indexes.py \
    tests/test_company_brain_retrieval_audit.py
All checks passed!

$ .venv/bin/python -m ruff format --check src/mari_kit/retrieval/indexes.py \
    tests/test_company_brain_retrieval_audit.py
2 files already formatted

$ .venv/bin/python -m pyright src/mari_kit/retrieval/indexes.py
0 errors, 0 warnings, 0 informations
```

## Limitations

- No network, installs, commits, or git mutations. `pyright` and `ruff` came
  from the pre-existing virtual environment; no dependency was added.
- Probing used bounded randomized fuzzing (200 seeds for exact-index filtering;
  500 seeds each for `BM25Index.with_deltas` and `ArtifactBM25Index.with_deltas`
  model checks) plus hand-built adversarial cases. It is not exhaustive.
- HNSW/IVF-PQ are approximate by design; only authorization safety (never
  return a disallowed id) and empty-allowlist behavior were asserted.
- Concurrent agents modified other tracked files
  (`.github/workflows/ci.yml`, `.gitignore`, `README.md`,
  `src/mari_kit/trajectories/workflows.py`) and added other
  `tests/test_company_brain_*.py` and `tests/test_revision_index_updates.py`.
  Those files were not edited. The collection error and any failures in them
  are outside this audit's ownership.
- The fixed tie-break aligns ranking with the adapters' existing `ref.key`
  ordering; it does not add a new ranking contract. The `HNSWIndex` finding
  remains open by design decision.
