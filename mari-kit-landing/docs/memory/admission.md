[]{#admission}[Reference]{.current-label}

# Knowledge admission and mutation planning

## Behavior

| Disposition | Meaning |
|---|---|
| `ACCEPT` | Evidence and authorization checks pass, and confidence reaches the accept threshold |
| `DEFER` | Evidence checks pass, and confidence lies in the review band |
| `REJECT` | Missing provenance, invalid evidence, unauthorized source, recalled input, or low confidence |
| `QUARANTINE` | Caller reports a secret or external instruction |

Mari applies caller-supplied signals and preserves reason codes. Signal
generation, novelty checks, and utility scoring belong to the application.


:::{collapse} Example admission decisions

| Candidate | Provenance | Injection signal | Decision |
|---|---|---|---|
| New user fact | Direct source evidence | None | Score for admission |
| Recalled model context | No new source evidence | None | Reject as circular evidence |
| External text containing instructions | External document | Present | Quarantine before confidence |
:::



Admission runs before reconciliation. Schema validity supplies one signal.
Safety and source authority have their own checks. Redundancy and support also
appear in the decision trace. Reconciliation runs for accepted candidates.

## How it works

`admit_candidate` applies a fixed precedence to supplied signals: quarantine
first, evidence and authorization rejection second, confidence thresholds last.
The booleans are caller assertions. Validate exact evidence and evaluate source
access before supplying them. A high confidence score alone leaves the other
checks intact.

Send accepted candidates to [mutation planning](memory-algorithms.md) using
caller-classified operations. The planner validates operations against existing
memory and returns a storage-free plan. The host controls the final commit.

::: source-block
**Papers and standards**

[Indirect prompt injection](https://arxiv.org/abs/2302.12173){.paper}[W3C PROV](https://www.w3.org/TR/prov-overview/){.paper}[Mem0: memory mutation operations](https://arxiv.org/abs/2504.19413){.paper}

[Mari implements disposition precedence. The host owns signal generation and commit boundaries.]{.small}
:::

```{code-block} python
:caption: Decide admission before calling a mutation planner

from mari_components.knowledge import (
    AdmissionDisposition,
    AdmissionSignals,
    AdmissionThresholds,
    admit_candidate,
)

decision = admit_candidate(
    AdmissionSignals(
        confidence=0.94,
        has_provenance=True,
        evidence_span_valid=True,
        source_authorized=True,
        recalled_input=False,
        contains_secret=False,
        contains_external_instruction=False,
    ),
    thresholds=AdmissionThresholds(accept=0.90, defer=0.65),
)

if decision.disposition is AdmissionDisposition.ACCEPT:
    mutation_plan = reconcile(candidate, current)  # application-injected policy
```
