# Validate and govern

Validation turns generated proposals into revision-bound knowledge. The modules resolve quoted evidence and inspect claims against their source revisions. They also support contradiction judgments, candidate selection, dependency invalidation, and explicit failure states.

## Governance operations


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
| Gate an untrusted write | `evaluate_write` | Disposition, reasons, and inherited taints |
| Resolve disagreeing sources | `resolve_assertions` | Working selection or explicit dispute |
| Expire derived knowledge | `plan_retention` | Delete, invalidate, and hold actions |

:::{collapse} Example evidence-validation example

| Proposed quote | Source revision | Resolution |
|---|---|---|
| `"30 days"` at offsets `31:38` | `refunds.md@8f31c2a` | Accepted when offsets and revision match |
| `"thirty days"` at offsets `31:42` | `refunds.md@8f31c2a` | Rejected: literal source text differs |
| `"30 days"` at offsets `31:38` | stale revision | Rejected: revision cannot identify current text |

```python
from mari_components.knowledge import parse_answer

answer = parse_answer(
    "How long is the refund window?",
    (document,),
    proposal,
)
```
:::

```{toctree}
:maxdepth: 1

document-contradiction
evidence
trust-writes
authority-conflicts
retention
freshness
workflows
verification
errors
```
