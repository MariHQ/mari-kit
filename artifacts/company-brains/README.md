# Company brain build and audit results

Twelve OpenCode sessions used `deepseek/deepseek-flash`: eight application
builders, three focused auditors, and one evidence-ambiguity fix agent.
The coordinator reviewed and integrated their changes, added missing APIs,
and reran the complete checks. Work is local and uncommitted.

## Delivered

Eight credential-free scenarios are available under
[`examples/company_brains`](../../examples/company_brains/README.md): search,
support, onboarding, incident response, decisions, conversation knowledge,
synchronization, and tenant isolation. Each exposes `run()` and a JSON CLI.
The combined runner is included in CI:

```bash
python -m examples.company_brains
```

[`results.json`](results.json) contains the combined scenario output.
[`existing-examples.json`](existing-examples.json) records the original
acceptance suite, with every check passing.

## Fixes and completed API gaps

| Finding | Integrated result |
| --- | --- |
| A stale exact intent hid a fresh near-match cached answer | Workflow selection searches eligible fresh caches first, then applies that candidate's impact gates; authorization remains enforced |
| Conflicting documents with the same ID silently overwrote one another in parsers | Shared lookup rejects ambiguity before parsing, independent of input order; identical duplicates remain valid |
| Short ellipsis-separated quotes were discarded | Resolver retains nonempty short fragments when no long fragments exist, then recomputes exact spans |
| Synthetic lexical IDs misordered tied structural refs beyond ten entries | Zero-padded internal IDs preserve structural ordering |
| Repeated dependencies duplicated freshness changes | Identical change rows are deduplicated without dropping distinct changes |
| Scoped revision lexical index lacked edit/delete support | Public `RevisionIndexDelta` and `RevisionBM25Index.with_deltas` support exact revision replacement/deletion; replacements preserve tenant, object, and unit identity |
| Legacy document evidence adaptation could not carry scope | Optional `scope` argument preserves host-supplied tenant identity |

Regression coverage includes stale replacements, immutable failed batches,
authorization revocation, new-document impact gates on alternative caches,
cross-tenant ambiguity, and rebuild-equivalent index updates.

## Verification

- Baseline: **530 tests passed**.
- Integrated suite on Python 3.13.3: **751 tests passed** (221 additional cases).
- All eight company-brain scenarios and the existing acceptance suite pass.
- Ruff lint and formatting checks pass.
- Pyright reports no errors or warnings.
- Wheel and source distribution build successfully.
- Clean installed-wheel checks verify imports, revision deltas, explicit evidence
  scope, and duplicate-document rejection outside the source checkout.
- `git diff --check` passes.

## Boundaries and remaining limitations

These are deterministic application fixtures, not deployed company services or
live-model quality evaluations. Production identity, authorization policy,
transactional persistence, model calls, connector scheduling, and semantic
validation remain host responsibilities.

Revision index updates rebuild the reference BM25 snapshot; they do not promise
sublinear updates. BM25 statistics cover the full corpus, so callers needing
statistics isolation should partition indexes. Approximate graph retrieval can
lose recall when authorization disconnects its search graph, while still
excluding forbidden results.

Legacy document-ID evidence and freshness are unscoped unless the host supplies
or preserves scope. Same-provider-revision ACL observations require a separate
host observation/live projection; the immutable reference document store does
not accept overwriting historical revisions. Sync transaction atomicity and
durability are supplied by the host adapter.

Per-agent Markdown reports retain original findings and intermediate results.
Their statements about pending fixes or temporary test failures are superseded
by this integrated report. Raw OpenCode transcripts and build logs remain local
and are excluded from version control.
