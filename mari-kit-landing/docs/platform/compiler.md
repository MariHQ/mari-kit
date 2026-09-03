[]{#compiler}[Proposed]{.proposed-label}

# Evaluation and compilation

A compiler would search pipeline and retrieval configurations against knowledge-system objectives and return a reviewable, versioned configuration proposal.

## How it works

Declare tunable parameters, hard constraints, and optimization metrics. For each candidate configuration, run the same frozen training cases, cache stage results by configuration/input fingerprints, reject any candidate that violates provenance, update fidelity, or ACL constraints, and rank feasible candidates on grounded recall, cost, and latency. Validate the selected configuration once on held-out cases; compilation returns a report and proposal, never a deployment side effect.

**Research basis**[DSPy](https://arxiv.org/abs/2310.03714){.paper} compiles parameterized LM pipelines against a declared metric. Mari generalizes the search space to retrieval, indexing, parsing, graph, consolidation, and packing configuration. Hard provenance, update-fidelity, and ACL constraints are Mari requirements and must be evaluated independently.

::::::::: metric-grid
<div>

**Grounded recall**maximize

</div>

<div>

**Provenance accuracy**require 1.0

</div>

<div>

**Update fidelity**require 1.0

</div>

<div>

**ACL leakage**require 0.0

</div>

<div>

**Context tokens**minimize

</div>

<div>

**Latency p95**minimize

</div>
:::::::::

```{code-block} python
:caption: proposed / compile.py

compiled = compile_knowledge_system(pipeline, trainset=train_cases,
    validation=validation_cases,  # optimizer may inspect these; never test_cases
    objectives={GroundedRecall(): Maximize(), ProvenanceAccuracy(): Require(1.0),
        UpdateFidelity(): Require(1.0), ACLLeakage(): Require(0.0),
        ContextTokens(): Minimize(), LatencyP95(): Minimize()},
    search_space=KnowledgeConfigSpace())

review(compiled.config, compiled.report, compiled.failures)
test_report = evaluate_once(compiled.config, cases=test_cases)
deploy(compiled.config, evidence=test_report)  # explicit application action
```
