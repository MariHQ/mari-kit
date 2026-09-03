[]{#admission}[Current]{.current-label}

# Knowledge admission and mutation planning

```{include} ../_includes/eval/memory.md
```

Admission is evaluated before reconciliation. A candidate may be valid JSON and still be unsafe, low-authority, redundant, or unsupported. Reconciliation runs only for accepted candidates.

## How it works

Run provenance, evidence-span, recalled-input, secret, external-instruction, authority, and confidence rules over the candidate. Aggregate rule results into `ACCEPT`, `DEFER`, `REJECT`, or `QUARANTINE` with reason codes. Only accepted candidates reach mutation reconciliation, which validates add, merge, supersede, retract, or unchanged operations against the current canonical slot without writing storage.

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
