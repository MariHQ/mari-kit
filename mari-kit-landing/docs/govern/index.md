# Validate and govern

Validation turns generated proposals into revision-bound knowledge. The modules resolve quoted evidence and inspect claims against their source revisions. They also support contradiction judgments, candidate selection, dependency invalidation, and explicit failure states.

## Governance operations


| Need | API | Returned evidence |
|---|---|---|
| Bind a claim to source text | `resolve_evidence` | Document, revision, section, offsets, quote |
| Reject unsupported answers | `parse_answer` | Grounded answer or explicit insufficiency |
| Localize a document contradiction | `validate_document_contradiction` | Judgment, sentence IDs, reference coverage |
| Score a training proposal | `document_contradiction_rewards` | Separate accuracy, coverage, and format rewards |
| Choose among generated candidates | `best_of_n`, `verdict_consensus` | Winner plus component scores |
| Assess recorded dependencies | `assess_freshness`, `assess_revision_refs` | Status and changed dependencies |
| Plan derived updates | `plan_dependency_updates` | Ready, reusable, waiting, and blocked outputs |
| Reuse a reviewed workflow | `match_reviewed_workflow` | Match plus rejection trace |
| Gate an untrusted write | `evaluate_write` | Disposition, reasons, and inherited taints |
| Resolve disagreeing sources | `resolve_assertions` | Working selection or explicit dispute |
| Expire derived knowledge | `plan_retention` | Delete, invalidate, and hold actions |

:::{collapse} Example evidence-validation example

| Proposed quote | Source revision | Resolution |
|---|---|---|
| `"30 days"` at offsets `31:38` | `refunds.md@8f31c2a` | Accepted when offsets and revision match |
| `"thirty days"` at offsets `31:42` | `refunds.md@8f31c2a` | Rejected: literal source text differs |
| Located citation bound to a stale revision | Current visible revision differs | Rejected by `validate_located_evidence` as outside visible references |

```python
from mari_components.knowledge import parse_answer

answer = parse_answer(
    "How long is the refund window?",
    (document,),
    proposal,
)
```
:::

`parse_answer` resolves quotes against the supplied documents and derives
coordinates and revisions itself. Use [located evidence validation](evidence.md)
for existing revision-bound citations. Use the [shared dependency planner](../start/dependency-updates.md)
to coordinate regeneration across modules.

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
