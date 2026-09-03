# Validate & govern

Validation turns generated proposals into revision-bound knowledge. These modules resolve quoted evidence, reject malformed or stale claims, localize document contradictions, select among candidate answers, invalidate derived work after source changes, and expose deliberate failure states.

## Choose a governance boundary


## Feature overview

| Need | API | Returned evidence |
|---|---|---|
| Bind a claim to source text | `resolve_evidence` | Document, revision, section, offsets, quote |
| Reject unsupported answers | `parse_answer` | Grounded answer or explicit insufficiency |
| Localize a document contradiction | `validate_document_contradiction` | Judgment, sentence IDs, reference coverage |
| Score a training proposal | `document_contradiction_rewards` | Separate accuracy, coverage, and format rewards |
| Choose among generated candidates | `best_of_n`, `evidence_consensus` | Winner plus component scores |
| Decide whether derived work is reusable | `freshness_status` | Status and changed dependencies |
| Reuse a reviewed workflow | `match_workflow` | Match plus rejection trace |

:::{collapse} Worked evidence-validation example

| Proposed quote | Source revision | Resolution |
|---|---|---|
| `"30 days"` at offsets `31:38` | `refunds.md@8f31c2a` | Accepted when offsets and revision match |
| `"thirty days"` at offsets `31:42` | `refunds.md@8f31c2a` | Rejected: not literal source text |
| `"30 days"` at offsets `31:38` | stale revision | Rejected: evidence no longer identifies current text |

```python
from mari_components.knowledge import parse_answer

answer = parse_answer(
    proposal,
    documents={document.document_id: document},
    sections={(section.document_id, section.section_id): section},
)
```
:::

```{toctree}
:maxdepth: 1

document-contradiction
evidence
freshness
workflows
verification
errors
```
