# Research foundations for the proposed API

> Historical design rationale. Several surfaces now have implementations, but
> the illustrative signatures below are not the current API reference. Consult
> the [feature docs](../mari-kit-landing/docs/index.md),
> [maturity labels](../mari-kit-landing/docs/start/maturity.md), and
> [shared dependency guide](dependency-updates.md) for current contracts.

This document records why each proposed Mari abstraction exists. The papers
and standards motivate observable behavior and evaluation requirements; they do
not prescribe the Python class names or signatures. Those are Mari design
choices and should remain replaceable until implementations and conformance
tests exist.

## Design map

| Proposed surface | Evidence from prior work | Consequence for Mari | Mari-specific choice to validate |
|---|---|---|---|
| `KnowledgeArtifact[T]` | W3C PROV models entities, activities, agents, derivation, revision, and responsibility. Nanopublications attach provenance and metadata to atomic assertions. | Identity, revision, evidence, derivation, and producing activity must be data, not log text. | One generic Python envelope across facts, decisions, summaries, procedures, and graph statements. |
| Store protocols | Database invariant-confluence work distinguishes operations that can execute without coordination from those whose invariants require it. | Store contracts must state atomicity, compare-and-swap, replay, isolation, and time-travel behavior rather than implying every backend is equivalent. | Small capability protocols plus a backend-neutral conformance suite. |
| Typed pipelines | Provenance research on ML pipelines shows that reconstructing a result requires inputs, transformations, configurations, and lineage across stages. Data-cascade research documents downstream failures caused by neglected data work. | Every stage must expose typed input/output, configuration identity, dependencies, failures, and a trace. Model output is a proposal before policy-controlled mutation. | `Pipeline[I, O]` composition and `ArtifactMutation` as the shared write boundary. |
| `RetrievalPlan` and `ContextEnvelope` | RAG uses explicit non-parametric memory to improve updateability and provenance. RRF and MMR support multi-retriever fusion and diversity. Long-context studies show that merely fitting evidence in a prompt does not ensure it is used. | Retrieval arms, fusion contributions, authorization, revisions, packing decisions, token budget, and final order must be inspectable and evaluated together. | A single envelope that carries excerpts, citations, dependency revisions, exclusions, and the complete retrieval trace. |
| Bi-temporal graph | Temporal knowledge-graph research represents facts that change over time; Zep reports benefits from maintaining historical relations for agent memory. | Mari must distinguish when a statement was valid from when the system observed or recorded it, and corrections must preserve history. | `query(at=..., known_at=...)` and interval-closing supersession semantics. |
| Procedural knowledge | Voyager stores reusable executable skills and improves them from environment feedback, execution errors, and self-verification. Reflexion stores verbal feedback in episodic memory for later trials. | A trajectory-derived procedure is a versioned candidate with its source runs and outcomes, not automatically active policy. | Held-out regression gates, interference suites, and explicit human promotion. |
| Knowledge-system compiler | DSPy demonstrates compiling parameterized LM pipelines against a metric rather than hand-tuning prompt strings. | Pipeline and retrieval choices can be a declared search space evaluated against explicit objectives. | Search over knowledge configuration, with hard provenance/update/ACL constraints and a reviewable configuration diff. |

## Unified artifacts

The proposed artifact envelope follows two established ideas:

- [W3C PROV](https://www.w3.org/TR/prov-overview/) makes provenance a graph of
  entities, activities, agents, usage, generation, derivation, and revision.
- [Nanopublications](https://arxiv.org/abs/1809.06532) demonstrate a
  domain-independent container for atomic assertions with assertion-level
  provenance and publication metadata.

Therefore an artifact should retain at least:

```python
KnowledgeArtifact(
    id=stable_logical_id,
    revision=immutable_revision_id,
    value=typed_value,
    scope=authorization_partition,
    evidence=source_spans,
    generated_by=activity_identity,
    derived_from=dependency_revisions,
    attributed_to=agent_or_reviewer,
    valid_time=domain_interval,
    transaction_time=system_interval,
    supersedes=prior_revisions,
)
```

Mari is not proposing to reproduce RDF or the complete PROV ontology. It should
provide a loss-aware mapping to PROV concepts so applications can export or
interoperate without making RDF a runtime dependency. Whether all artifact
types fit one envelope is an implementation hypothesis and must be tested
against facts, decisions, summaries, answers, and procedures.

## Storage protocols

[Coordination Avoidance in Database
Systems](https://arxiv.org/abs/1402.2237) shows that safe coordination choices
depend on application invariants. Consequently, a protocol containing methods
named `apply` or `commit` is insufficient: Mari has to publish the invariants a
backend preserves and test them.

The proposed conformance profile is:

```text
Sync commit     plan changes + next cursor are atomic
Optimistic write expected_generation prevents lost updates
Replay          repeating an accepted event is idempotent
Isolation       tenant/scope filters apply before scoring or traversal
Time travel     point-in-time reads return the requested recorded state
Deletion        tombstone, retraction, and physical purge are distinct
Projection      a failed rebuild cannot replace the last valid read version
Ordering        equal inputs produce stable observable ordering
```

Different backends may advertise different capability sets. Mari should not
claim that an eventually consistent vector service and a transactional artifact
database have identical semantics. The Python `Protocol` split and exact test
fixtures are Mari engineering choices derived from these invariants, not an
algorithm from the paper.

## Typed, traceable pipelines

[Machine Learning Pipelines: Provenance, Reproducibility and FAIR Data
Principles](https://arxiv.org/abs/2006.12117) motivates capturing the conditions
needed to reproduce a pipeline result. [Data
Cascades](https://doi.org/10.1145/3411764.3445518) provides empirical evidence
that upstream data problems can create delayed, compounding downstream failure.

For Mari, a stage should therefore have a value contract and an observation
contract:

```python
class Stage(Protocol[InputT, OutputT]):
    @property
    def identity(self) -> StageIdentity: ...  # code/config/model/schema versions

    def run(self, value: InputT, *, scope: KnowledgeScope) -> StageResult[OutputT]:
        """Return value, dependencies, measurements, warnings, and failures."""
```

Traces must join across stages by artifact and revision IDs. A failed parser or
review gate must remain observable instead of disappearing because it emitted
no mutation. The exact generic types and composition operators are Mari API
design; reproducibility and causal diagnosis are the research-backed
requirements.

## Retrieval plans and context envelopes

[Retrieval-Augmented Generation](https://arxiv.org/abs/2005.11401) identifies
provenance and knowledge updates as reasons to use explicit non-parametric
memory. [RAG-Fusion](https://arxiv.org/abs/2402.03367) applies reciprocal-rank
fusion across multiple retrievals, while [maximal marginal
relevance](https://www.cs.cmu.edu/afs/cs/Web/People/jgc/publication/MMR_DiversityBased_Reranking_SIGIR_1998.pdf)
balances relevance and novelty. [Lost in the
Middle](https://arxiv.org/abs/2307.03172) shows that evidence position can
materially affect model performance even when the evidence fits in context.

Those findings require a context object to preserve more than rendered text:

```python
ContextEnvelope(
    excerpts=(...),
    evidence=(...),
    dependency_revisions=(...),
    arm_results=(...),
    fusion_contributions=(...),
    exclusions=(...),
    packing_order=(...),
    token_count=...,
)
```

Authorization and time filters belong before fusion, graph propagation, or
model-visible rendering. Packing must be benchmarked with order perturbations,
budget sweeps, answer-support recall, citation correctness, and leakage tests.
The unified envelope is Mari's proposed integration boundary; no cited paper
establishes it as the uniquely correct interface.

## Bi-temporal graph

[Zep](https://arxiv.org/abs/2501.13956) describes a temporally aware knowledge
graph that maintains historical relationships for agent memory. The broader
[temporal knowledge-graph completion
survey](https://arxiv.org/abs/2201.08236) catalogs representations and tasks for
facts whose truth changes over time.

Mari's proposed API distinguishes:

```text
valid time        when the statement applied in the represented domain
transaction time  when this revision was recorded by the knowledge system
```

Thus `query(at=t1, known_at=t2)` can answer both “what applied then?” and “what
did the system know then?” A late correction inserts a new recorded revision;
it does not rewrite the audit history. The exact interval types, open-boundary
rules, and contradiction policy need dedicated truth-table and property tests.

## Procedural knowledge

[Voyager](https://arxiv.org/abs/2305.16291) demonstrates an expanding library of
temporally extended, compositional skills improved through environment
feedback, execution errors, and self-verification. [Reflexion](https://arxiv.org/abs/2303.11366)
demonstrates using verbal feedback retained in episodic memory to improve later
trials.

These results motivate storing procedures and reflections. They do not justify
automatically promoting a procedure learned from a successful trace. Mari adds
that governance boundary:

```text
source trajectories -> candidate -> held-out evaluation -> review -> active revision
                              |             |
                              |             +-- related skills + known failures
                              +-- never executable merely because it was generated
```

The evaluation must include task success, tool correctness, grounding, cost,
known failures, and cross-procedure interference. Human promotion and these
specific regression gates are conservative Mari policies, not claims made by
Voyager or Reflexion.

## Evaluation and compilation

[DSPy](https://arxiv.org/abs/2310.03714) treats LM programs as parameterized
modules and compiles a pipeline to maximize a metric. Mari generalizes the
search target from demonstrations and prompts to knowledge-system parameters:
retrieval arms, fusion weights, index parameters, graph expansion, parser
thresholds, consolidation policy, and context packing.

```python
compiled = compile_knowledge_system(
    pipeline,
    trainset=train_cases,
    validation=validation_cases,
    objectives={
        GroundedRecall(): Maximize(),
        ProvenanceAccuracy(): Require(1.0),
        UpdateFidelity(): Require(1.0),
        ACLLeakage(): Require(0.0),
        ContextTokens(): Minimize(),
        LatencyP95(): Minimize(),
    },
)
final_report = evaluate_once(compiled.config, held_out_test_cases)
```

The compiler must record the search space, trials, seeds, model/index versions,
cost, and selected configuration. The held-out test set is not optimizer input.
Hard ACL, provenance, and update-fidelity constraints are Mari requirements;
DSPy provides backing for declarative optimization, not proof that these
particular objectives or thresholds are sufficient.

## Acceptance criteria before implementation is called stable

Each proposed surface needs:

1. Executable invariants and adversarial conformance fixtures.
2. At least two substantially different backend or strategy implementations.
3. Ablations showing that the abstraction retains the information required by
   its backing method.
4. Corpus-size, context-budget, update, temporal, and authorization evaluation.
5. Versioned traces sufficient to reproduce a result or explain why it cannot
   be reproduced.

These were the original acceptance targets. Current maturity is recorded per
surface in the feature documentation, rather than inferred from this proposal.
