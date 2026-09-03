[]{#admission}[Current]{.current-label}

# Knowledge admission and mutation planning

## Behavior

| Disposition | Meaning |
|---|---|
| Admit | Evidence, trust, novelty, and utility clear the configured thresholds |
| Review | Potentially useful, with one or more uncertain signals |
| Reject | Unsafe, ungrounded, duplicate, or below the utility floor |

Mari applies caller-supplied signals and preserves the decision trace. It evaluates caller-supplied safety and utility signals.


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

Run the configured admission rules over each candidate. They can inspect
provenance, evidence spans, and recalled inputs. Other rules cover secrets,
external instructions, authority, and confidence. Aggregate their results into
`ACCEPT`, `DEFER`, `REJECT`, or `QUARANTINE` with reason codes. Accepted
candidates reach mutation reconciliation. That function checks the proposed
operation against the current canonical slot and returns a storage-free plan.

::: source-block
**Papers and standards**

[Indirect prompt injection](https://arxiv.org/abs/2302.12173){.paper}[W3C PROV](https://www.w3.org/TR/prov-overview/){.paper}[Mem0: memory mutation operations](https://arxiv.org/abs/2504.19413){.paper}

[Disposition precedence and commit boundaries are proposed Mari contracts.]{.small}
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
