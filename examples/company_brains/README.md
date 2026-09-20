# Company brains

Eight runnable adoption scenarios compose Mari Kit's public APIs into small
company knowledge applications. Each uses synthetic company documents and
deterministic model output; no credentials or external services are required.

From the repository root, with the development dependencies installed:

```bash
python -m examples.company_brains
python -m examples.company_brains.search
pytest -q tests/test_company_brain_*.py
```

The combined runner emits JSON containing each scenario's observable results.
The tests assert expected behavior, including failure paths.

The [persistent application](durable/README.md) extends these scenarios with
SQLite transactions, process-death recovery tests, changing permissions,
live-model quality evaluation, and scale/recall benchmarks.

| Scenario | Workflow |
| --- | --- |
| `search` | Cross-source search, cited answers, edits, and deletion |
| `support` | Reviewed answer reuse, changed policies, and revoked access |
| `onboarding` | Employee policy facts and section-level evidence freshness |
| `incident` | Runbook dependencies and selective invalidation |
| `decisions` | Decision evidence, review, and revision history |
| `conversation` | Conversation extraction, caching, and source evidence |
| `sync` | Paginated snapshots, incremental changes, and transaction generations |
| `isolation` | Tenant-scoped identities and per-user access boundaries |

These fixtures demonstrate library composition, not a deployed service.
The host application supplies identity and authorization decisions, durable
transactional persistence, model calls, embeddings, and connector scheduling.
Exact citation validation checks source material; semantic correctness and
publication approval remain application responsibilities.

## Maintaining a scoped search index

`RevisionBM25Index.with_deltas` applies revision-checked edits and deletions to a
new snapshot. A replacement must retain the same scoped object and unit; a stale
`previous_ref` raises before the original index changes. The `search` scenario
uses this path. Like the other reference lexical indexes, this rebuilds BM25
statistics; it is not a sublinear update algorithm.

```python
from mari_kit.retrieval import IndexOperation, RevisionIndexDelta

updated = index.with_deltas(
    [
        RevisionIndexDelta(
            ref=new_document.ref_in(scope),
            previous_ref=old_document.ref_in(scope),
            operation=IndexOperation.UPSERT,
            text=new_document.body,
        ),
    ]
)
```

## Evidence and authorization boundaries

Document-based parsers reject conflicting documents with the same `document_id`.
Pass one current revision per identity, within the host-authorized scope; use
scoped `RevisionRef` and `LocatedEvidence` when combining tenants. Identical
repeated documents remain accepted.

When adapting legacy document evidence, use
`document_evidence_ref(evidence, scope=scope)` to retain tenant identity. Without
that argument the adapter remains unscoped. Likewise, legacy document-ID
freshness maps should be built per tenant; `assess_revision_refs` is the
structural-reference alternative.

Authorization filters exclude forbidden results before scoring. BM25 corpus
statistics still describe the full index; use separate indexes when corpus
statistics must also be isolated. Positive lexical scores indicate term overlap,
not that an answer is semantically supported. The search example abstains when
all authorized hits have zero scores.
