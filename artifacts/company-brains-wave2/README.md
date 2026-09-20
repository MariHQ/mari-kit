# Company brain wave 2 — integrated results

Twelve OpenCode `deepseek/deepseek-flash` agents worked as builder, breaker,
and reviewer teams for durability, permissions, quality, and scale. The
coordinator integrated fixes, ran actual model calls and larger benchmarks,
and completed final verification. Changes remain local and uncommitted.

## Persistent application

[`examples/company_brains/durable`](../../examples/company_brains/durable/README.md)
contains a SQLite-backed reference application. Live documents, the durable
text projection, and sync checkpoints commit atomically. Group memberships and
answer caches survive restart. Same-revision ACL observations update the live
state without overwriting historical observations.

```bash
python -m examples.company_brains.durable --db /tmp/company-brain.sqlite
```

Process-death tests reopen from a fresh process after interruption at four
transaction stages. Competing writers test the generation check under a real
process race. Independent tests cover serialization, pagination/resume,
rollback, tenant separation, and updates observed through another connection.

The [fixture lifecycle](durable-fixture.json) and
[actual DeepSeek lifecycle](live-durable.json) both pass all ten checks:
restart/cache reuse, group revocation, retaining another user's access,
source edit, same-revision ACL revocation, newly granted access, deletion, and
projection consistency. The live lifecycle made **seven answer and seven
extraction calls**, with cache hits avoiding calls.

## Integrated fixes

- A contention-induced abstention could persist in the cache after sources
  stabilized. Exhausted retries now remain uncached; regression coverage proves
  the next stable request can answer.
- Cache fingerprints now use full canonical source fingerprints, including
  titles and other metadata used by retrieval, rather than a partial custom
  encoding. A title-only edit invalidates a persisted cache after restart.
- The store rejects malformed generation transitions as well as foreign-source
  writes and stale expected generations before committing any changes.
- The corpus distinguishes authorized revisions explicitly, keeps grading
  fields out of prompts, and includes revision-aware evidence labels.
- Corpus review corrected unstated authority assumptions, an incorrectly
  labeled gift-card question, and an ambiguous single-deadline question.
- Benchmark reporting separates prebuilt reference-index timing from repeated
  application timing, labels small-sample percentiles, includes WAL/SHM in
  storage footprint, sweeps allowlist sizes, and exposes full-manifest writes.
- Fixture quality evaluation now has a working JSON CLI; its executable
  regression test prevents a silently empty report.

## Live quality results

The [final frozen corpus](quality-corpus.json) matches the SHA-256 recorded in
[the live report](live-quality.json). It contains 25 synthetic cases across
current/superseded policy, conflict, ambiguity, missing information, restricted
evidence, and irrelevant matches. Expected labels never reach the model.

| Measure | Final live result |
| --- | --- |
| Answer requests completed | 25 / 25 |
| Answer/abstention disposition agreement | 23 / 25 |
| Lexical correctness proxy on answerable cases | 10 / 10 |
| Valid citations among emitted grounded answers | 12 / 12 |
| Required abstentions produced | 13 / 15 |
| Stale-answer signals among grounded attempts | 0 / 12 |
| Extraction batches completed and validated | 24 / 25 |

The two disposition disagreements were a legal-versus-sales NDA conflict and
a regional refund question answered conditionally. They demonstrate the gap
between citation validity and compliance with a conservative abstention policy;
they are not proof of fabricated facts.

One extraction hit the 3,000-token output limit. A separately recorded
[6,000-token retry](extraction-retry.json) produced two validated facts. The
first-pass report still records the failure. Of the 24 accepted first-pass
extraction batches, 15 were nonempty and yielded 25 validated facts; empty
extractions are not counted as factual successes.

The [deterministic extractive baseline](fixture-quality.json) agrees with the
disposition rubric on 14/25 cases and meets the lexical correctness proxy on
7/10 answerable cases. Positive lexical overlap alone does not decide whether
an answer is warranted.

The [initial live run](live-quality-initial.json) is preserved. Its labels had
the corpus issues described above; the final run used the corrected corpus.
This is a development evaluation with inspected fixtures, not a held-out
benchmark. Exact quotation and term matching do not establish semantic
entailment. The static superseded-policy cases withhold old revisions; the
durable lifecycle separately tests actual source edits and cache invalidation.

## Scale and recall

[Scale measurements](scale.json), 20 queries per size, one machine, allocation
tracing disabled for wall-time measurements:

| Documents | Repeated application search p50 / p95 | Cached answer p50 / p95 | Durable footprint |
| --- | --- | --- | --- |
| 1,000 | 22.8 / 24.0 ms | 21.0 / 21.2 ms | 3.0 MiB |
| 10,000 | 245.9 / 302.6 ms | 213.6 / 262.6 ms | 29.3 MiB |
| 25,000 | 735.1 / 778.1 ms | 538.4 / 665.7 ms | 72.8 MiB |

At 25,000 documents, prebuilt reference-index query p95 was 147.7 ms,
single-shot cold index construction was 245.6 ms, and batch edit index rebuild
was 270.7 ms. Process-lifetime peak RSS reached 475.2 MiB across the sequential
size sweep. These are observations, not SLAs or per-phase allocation figures.
The separate [traced allocation run](scale-allocations.json) records Python
allocation peaks without presenting its instrumented timings as the main result.

The application currently reads the tenant's full current snapshot, authorizes
it, and rebuilds the reference index for searches. Cached answers still read and fingerprint source
observations. The measurements expose those costs rather than claiming a warm,
sublinear application path. Sync also serializes each source's full manifest.

The [1,000-vector recall experiment](recall-1000.json) found zero unauthorized
hits, but HNSW recall@10 was 11.0%, 6.5%, and 24.5% for allowlists of 10, 50,
and 200 items respectively. Full-corpus recall was 72% at `ef_search=64` and
95% at 256. Increasing `ef_search` did not repair the sparse disconnected
allowlist case. The durable application uses lexical retrieval; these results
limit confidence in choosing the optional reference HNSW adapter for restricted
company search. Lexical edits/deletions matched a clean rebuild in all probes.

## Verification and limits

- **944 tests pass**, up from 751 at the start of this wave (193 additional cases).
- Ruff lint and formatting checks pass; Pyright reports no errors or warnings.
- Both example suites and the persistent fixture run pass.
- Wheel and source distribution builds pass; the durable demo also runs against
  the installed wheel in a separate Python 3.13 environment.
- `git diff --check` passes. Live provider calls stay outside CI.

This is a reference application, not a deployed production service. Identity
authentication, migrations, backup/restore, encryption, retention and operational
monitoring remain host work. Crash tests cover process death, not physical power
loss. Custom model prose is not semantically verified merely because its
citations are valid. The next concrete engineering priorities are an indexed
change/authorization frontier for cache checks, a production retrieval adapter
with measured restricted-query recall, and an independently reviewed quality
set with explicit authority and abstention rules.

Per-agent reports preserve intermediate findings. This integrated report
supersedes their pending-fix and transient-failure statements. Raw transcripts,
logs, and SQLite files stay local and are ignored by version control.
