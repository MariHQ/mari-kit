[]{#memory-evaluation}[Proposed]{.proposed-label}

# Long-horizon memory evaluation

```{include} ../_includes/eval/platform.md
```

A memory system needs separate measurements for writing, updating, retrieving, temporal reasoning, abstaining, and respecting context limits. One aggregate answer score hides which subsystem failed.

## How it works

Freeze conversations, source revisions, expected evidence, and change events into cases. Replay each case under several corpus sizes and context budgets. Score extraction at write time, evidence recall at query time, cross-session synthesis, ordering and date reasoning, correction after source updates, abstention when evidence is absent, and ACL leakage. Store per-stage traces with every score so a regression points to the responsible parser, index, policy, or packing decision.

::::::::: metric-grid
<div>

**Extraction**precision · recall · evidence

</div>

<div>

**Retrieval**recall@k · rank · authorization

</div>

<div>

**Synthesis**support · completeness

</div>

<div>

**Temporal**order · valid time · updates

</div>

<div>

**Abstention**unsupported-answer rate

</div>

<div>

**Operations**tokens · latency · refresh work

</div>
:::::::::

```{code-block} python
:caption: proposed / memory_eval.py

report = evaluate_memory_system(system, cases,
    corpus_sizes=(100, 10_000, 1_000_000),
    context_budgets=(2_000, 8_000, 32_000),
    metrics=[ExtractionF1(), EvidenceRecall(k=10), UpdateFidelity(),
             TemporalAccuracy(), AbstentionPrecision(), ACLLeakage()])

report.by_capability["updates"]
report.failures  # case, stage, revisions, trace, observed output
```

::: source-block
**Paper**

[LongMemEval: five long-term memory capabilities](https://arxiv.org/abs/2410.10813){.paper}

[The multi-scale replay matrix and ACL/update constraints are proposed Mari evaluation requirements.]{.small}
:::
