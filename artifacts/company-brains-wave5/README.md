# Company brains: fifth wave and publication

Three parallel OpenCode `deepseek/deepseek-flash` agents worked on compact cache
records, multiprocess durability tests, and publication review. The coordinator
added an independent no-corpus-scan regression, measured the final application,
and verified the accumulated implementation before publication.
[Agent sessions](sessions.json).

## Changes

- Cache schema v3 stores a fixed-width SHA-256 digest of the authorized source
  set instead of the full fingerprint list. Views compute the digest once and
  retain a document-ID lookup, included in retained-memory accounting. Warm hits
  no longer rebuild that lookup or scan authorized documents. Cold and
  invalidated views still load, authorize, and fingerprint the corpus.
- Every hit still checks current access counters, request identity, scope,
  checksum, dependencies, revision labels, and exact quotes. Legacy v1/v2 records
  are safe misses and are regenerated. Source data and sync state are preserved.
- Four new multiprocess tests use independent SQLite connections and explicit
  synchronization events: competing writers at one generation, acknowledged
  cross-process permission/source changes, restart during paginated full sync,
  and rollback. No shared-connection thread-safety assumption is introduced.
- The coordinator's regression forbids iterating the authorized document tuple
  during a warm hit. Another test shows an otherwise identical answer record has
  exactly the same serialized size with one source or 151 authorized sources.

## Measurements

Same deterministic scale workload as earlier waves, 20 query samples per size,
allocation tracing off. [Raw results](scale.json).

| Documents | Search p95 | Cached-answer p95 |
| --- | ---: | ---: |
| 1,000 | 4.431 ms | 0.048 ms |
| 10,000 | 45.076 ms | 0.046 ms |
| 25,000 | 246.163 ms | 0.052 ms |

At 25,000 documents, the previous wave's cached-answer p95 was 31.933 ms. This
wave removes corpus-size-dependent work from an unchanged hit. Work still
depends on answer/evidence size and quote validation within cited source text;
these are local sequential fixture measurements, not production latency SLAs.

## Validation

**1,102 tests pass**, up from 1,079. The fifth-wave focused tests pass 23 cases.
Ruff lint/format and Pyright pass. Wheel/sdist build, installed-wheel durable
demo, original examples, all eight first-wave scenarios, deterministic durable
lifecycle, strict Sphinx build, and browser sidebar checks pass.

The publication review identified the generated inventory's source-revision
dependency: it must be regenerated after committing source changes, then
committed separately without another source edit. The previous upstream CI
failure was precisely this stale-inventory check; its Python, wheel, and solver
jobs passed. The publication sequence follows that requirement.

Raw agent transcripts, logs, and SQLite databases are ignored. Candidate files
were checked for environment-secret values; none were found. Curated reports
contain synthetic example/evaluation data and historical measurements.

## Reproduce

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m examples.company_brains.durable
.venv/bin/python -m benchmarks.company_brain_scale --sizes 1000 10000 25000 \
  --queries 20 --no-tracemalloc --output /tmp/brain-scale.json
```

## Compatibility and limits

Across the accumulated waves, new core retrieval controls are keyword-only with
backward-compatible defaults. Intentional behavioral corrections include
rejecting conflicting duplicate document IDs in evidence parsers, deterministic
structural tie ordering beyond nine units, selecting fresh reviewed workflow
caches, and deduplicating freshness changes.

The durable host continues to trust its caller's identity and database writers.
The checksum is unkeyed and does not authenticate writers or prove semantic
truth. Memory accounting estimates retained Python objects, not total RSS or
temporary allocations. All writers must maintain access counters through the
host methods; database replacement/restore requires new brain instances.
Multiprocess tests establish SQLite host behavior, not a distributed deployment.

This wave does not change the prompt or claim new model-quality results. Prior
live evaluations remain in their respective wave reports.
