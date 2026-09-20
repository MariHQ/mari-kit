> Agent handoff report. See [integrated results](README.md) for coordinator fixes and final verification.

> Agent handoff report. See the coordinator's integrated results for final
> validation and publication handling.

# Wave 6: interleaved multi-user workload on the company brain

Owner: `workload` agent. Files changed:

- `benchmarks/company_brain_interleaved.py` (new)
- `tests/test_brain6_workload.py` (new, 28 tests)
- `artifacts/company-brains-wave6/workload.md` (this report)

No other source file, test, benchmark, dependency, credential, or git state was
touched. `examples/company_brains/durable/engine.py` and `store.py` were left
exactly as found. No install, network access, or commit was performed.

## Problem

The wave-3/4/5 view cache is keyed by `(scope, user, token)` and bounded by an
LRU count plus an estimated retained-byte budget. Whether a request is a cache
hit therefore depends not only on how many users are served but on **when** each
user is served. A service that groups one user's questions together keeps that
user's authorized view resident; a service that interleaves users under the same
bounds pays repeated view rebuilds. The benchmark exists to measure that effect
on the real `CompanyBrain` + `SQLiteBrainStore` pair with honest, counted
statistics.

## Design

### Deterministic corpus and request multiset

The benchmark consumes the existing deterministic helpers unchanged:

- `benchmarks/company_brain_scale.build_documents` for the corpus;
- `benchmarks/company_brain_cache_memory.build_users` and `build_user_queries`
  for mixed-team users and lexical queries.

For one `(documents, users, queries_per_user, seed)` it builds the exact
`(user_id, query)` multiset and then emits it in three orders:

| Ordering | Definition |
| --- | --- |
| `consecutive` | each user's queries run back to back before the next user |
| `round_robin` | one query per user, cycling by query index |
| `hot_interleaved` | the hot user's queries are spread through the run, separated by even blocks of cold-user traffic (whole users per block) |

All three are permutations of the same multiset, asserted at runtime and
summarized by a SHA-256 fingerprint of the sorted request list. Any difference
in the cache metrics is therefore attributable to interleaving alone.

### Counted, not assumed, misses and hits

Each strategy gets its own fresh temporary SQLite database, seeds the corpus and
group memberships, and constructs a fresh `CompanyBrain`. A `_CountingStore`
subclass overrides `access_token` and `access_token_snapshot` and increments a
counter before delegating. The engine calls `access_token_snapshot` only when
the cheap token is not already cached, and one miss rebuilds exactly one
authorized view, so:

- `view_misses` = counted `access_token_snapshot` calls;
- `view_hits` = `requests - view_misses`;
- `hit_rate` = `view_hits / requests`.

There are no synthetic hit counts. `access_token_reads` (the cheap token reads)
is recorded for context. Each request is
`CompanyBrain.search(query, user_id=..., limit=...)`.

### Bounds and latency

`CompanyBrain.cache_stats()` supplies retained views, retained estimated bytes,
evictions, and evicted estimated bytes. The report records whether the
configured `view_cache_size` count bound and `view_cache_bytes` retained-byte
budget held. Retained bytes are the engine's explicit object-size estimate, not
RSS. Per-request wall time is sampled with `perf_counter`; the report uses the
existing `company_brain_scale.latency_summary` (count, p50, p95, min, max,
`p95_valid`). No machine-time threshold is applied.

### CLI

Defaults: `--documents 240 --users 16 --queries-per-user 4 --limit 5 --count 8
--budget 2097152 --seed 20240919`; `--hot-user` selects the hot user (default
the first), `--no-byte-budget` disables the byte bound, and `--output` /
`--workdir` control reporting. The reusable `run(...)` returns the full report;
`deterministic_signature(report)` strips wall samples for equality checks.

## Measured results

Defaults, one machine, informational only. 64 requests per strategy, 64 latency
samples each, `p95_valid` true. Authorized documents per user: min 187, max 240,
mean 217.438. Request multiset fingerprint
`c2da564c27aa3cf2090b34f50f085a0c651a95446dc37d39a402a521e8aadd8c` is identical
across all three orderings.

### Default run: `--count 8 --budget 2 MiB`

The byte budget is the binding bound here (two ~1 MB views fit; the count slack
is 8), which makes interleaving evictions visible.

| Ordering | Requests | User switches | Misses | Hits | Hit rate | Final views | Retained bytes | Evictions | p50 ms | p95 ms | Bounds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `consecutive` | 64 | 15 | 16 | 48 | 0.7500 | 2 | 1,995,581 | 14 | 1.039 | 23.319 | held |
| `hot_interleaved` | 64 | 21 | 22 | 42 | 0.6563 | 2 | 1,995,357 | 20 | 1.137 | 23.489 | held |
| `round_robin` | 64 | 63 | 64 | 0 | 0.0000 | 2 | 1,995,357 | 62 | 20.193 | 23.252 | held |

Reading:

- Grouping each user's four queries rebuilds each view exactly once (16 misses =
  16 users) despite a two-view budget, because nothing can evict the user's own
  view inside their block.
- Spreading the hot user through cold-user blocks rebuilds the hot view six
  extra times (22 misses); the hot user keeps a 0.6563 hit rate, clearly better
  than round-robin but worse than grouping.
- Cycling one query per user evicts every view before its next turn: 64 misses,
  0 hits. Half the requests pay a full BM25 rebuild, which is also visible in the
  p50 (20.2 ms vs ~1.0 ms for a warm read); p95 is similar across orderings
  because the rebuild tail dominates.

### Count-only run: `--count 8 --no-byte-budget`

With the byte budget removed, the count bound holds 8 views (~8.6 MB). The hot
user's blocks never introduce more than eight distinct users between hot
requests, so the hot view survives and matches grouping:

| Ordering | Misses | Hits | Hit rate | Final views | Retained bytes | Evictions | Bounds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `consecutive` | 16 | 48 | 0.7500 | 8 | 8,634,463 | 8 | held |
| `hot_interleaved` | 16 | 48 | 0.7500 | 8 | 8,463,742 | 8 | held |
| `round_robin` | 64 | 0 | 0.0000 | 8 | 8,633,183 | 56 | held |

### Tight-byte run: `--count 8 --budget 1 MiB`

A one-megabyte budget retains a single view, so even consecutive grouping
thrashes after each user (52 misses, 0.1875):

| Ordering | Misses | Hits | Hit rate | Final views | Retained bytes | Evictions | Bounds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `consecutive` | 52 | 12 | 0.1875 | 1 | 1,032,692 | 51 | held |
| `hot_interleaved` | 52 | 12 | 0.1875 | 1 | 1,032,692 | 51 | held |
| `round_robin` | 64 | 0 | 0.0000 | 1 | 1,032,692 | 63 | held |

In all three runs every strategy reported `within_count_bound`,
`within_byte_budget`, and `within_bounds = true`, with `views <= count` and
`retained_estimated_bytes <= budget`.

## Tests

`tests/test_brain6_workload.py` adds 28 tests:

- the three orderings are exact full-count permutations of one multiset with
  distinct user-adjacency profiles, and the hot user's requests are non-adjacent;
- the report carries the full request count, equal multisets, consistent
  `misses + hits == requests`, and one latency sample per request;
- cache stats are consistent with the configured count and byte bounds;
- grouping rebuilds each view once while capacity-bound round-robin misses
  every request, and hot interleaving is no better than grouping;
- a one-byte budget and a zero count bound evict everything while still holding
  their bounds, and the byte budget can be disabled;
- two runs have equal `deterministic_signature` (counts, orderings, cache
  stats), with only wall samples excluded;
- invalid arguments are rejected by `run(...)` and by the CLI, and the CLI
  writes a configured report including `--no-byte-budget`.

## Verification

- `benchmarks/company_brain_interleaved.py` and
  `tests/test_brain6_workload.py`: `ruff check` clean.
- `tests/test_brain6_workload.py`: 28 passed.
- Full suite (`.venv/bin/python -m pytest -q`): **1140 passed** (1102 baseline,
  plus this file and concurrently added wave-6 tests).

## Notes / residual

- The measured `p50`/`p95` values are machine-specific and informational; the
  benchmark deliberately makes no timing assertion.
- `retained_estimated_bytes` is the engine's explicit estimate and the budget
  uses the same number, so it is not a process RSS cap.
- Every strategy seeds its own temporary database, so results cannot be
  contaminated by another strategy's durable answer cache.
- All 64 requests in each ordering are distinct `(user, query)` pairs; the
  durable answer cache is not the variable under study, the authorized-view
  cache is.
