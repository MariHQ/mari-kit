[]{#context-lifecycle}[Supported]{.current-label}

# Context lifecycle and selective intervention

## Behavior

| Comparison | Result | Design consequence |
|---|---:|---|
| Proactive memory agent vs. base agent, Terminal-Bench 2.0 | +8.3 percentage points | Recall must be able to intervene before a model call |
| Proactive memory agent vs. base agent, tau2-Bench | +6.8 percentage points | Intervention policy has its own evaluation |
| PlugMem | Evaluates utility relative to context consumed | Record tokens and selected knowledge alongside task accuracy |

The table reports upstream results. Use those values when planning measurements
of selective injection. The application supplies its model and agent loop.

:::{collapse} Known-answer disclosure checks

| Case | Expected | Observed |
|---|---|---|
| Incident condition: matching / non-matching facts | `true / false` | `true / false` |
| Seven-token progressive budget | index + summary | index + summary selected. Source skipped |

The checks cover predicate and budget semantics. Retrieval relevance and
authorization require separate evaluations.
:::

## How it works

Mari separates four records:

1. `SessionEvent` is the durable sequence of messages, tools, results, and errors.
2. `ContextRequest` describes the next model call, its purpose, scope, and budget.
3. `ContextEnvelope` contains the knowledge selected for that call, with inclusion and exclusion traces.
4. `MemoryUpdatePlan` proposes changes after a model or tool event completes.

The provider accepts `ABSTAIN` as a result. Silence is a successful decision
when retrieved knowledge is weak or redundant. Authorization and freshness can
also block injection. Cost policy handles cases where predicted utility falls
below the retrieval expense.

:::::::::{container} diagram flow
:::{container} card
**Observe**
Tool result or session event
:::
**→**
:::{container} card
**Retrieve**
Authorized candidates
:::
**→**
:::{container} card
**Decide**
Inject or abstain
:::
**→**
:::{container} card
**Measure**
Outcome and context cost
:::
:::::::::

```{code-block} python
:caption: Put Mari around a framework-owned model call

from mari_components.lifecycle import ContextRequest, LifecycleEvent, LifecyclePhase

request = ContextRequest(
    request_id="answer-refund-17",
    query="Can this order still be refunded?",
    purpose="customer_support",
    scopes=("user:42", "project:support"),
    token_budget=1_200,
)

envelope = await provider.before_model(request)
response = await model(user=request.query, context=envelope.text)
plan = await provider.after_model(
    LifecycleEvent(
        phase=LifecyclePhase.AFTER_MODEL,
        request_id=request.request_id,
        content=response,
    )
)
```

## API boundary

`ContextProvider` is an async protocol with `before_model`, `after_model`, `after_tool`, and `end_session`. Mari owns the values passed through that boundary. The host owns model execution, retry policy, persistence, and whether an accepted update plan is committed.

## Measures

| Measure | Question |
|---|---|
| Intervention precision | What fraction of memory injections helped? |
| Missed-intervention rate | What fraction of useful available memory was withheld? |
| Utility per 1,000 tokens | Did the result improve enough to justify the context? |
| Unsupported-memory rate | Did injected material lack valid evidence? |
| Task success delta | Did the same task improve with the provider enabled? |

## Check evidence sufficiency before answering

An answer can contain citations and lack a required part. Mari
keeps query decomposition, evidence assessment, and follow-up retrieval
separate.

```{code-block} python
:caption: Retrieve for unresolved requirements

from mari_components.retrieval import (
    RequirementAssessment, RequirementStatus,
    assess_context_sufficiency, parse_information_requirements,
    parse_retrieval_gap_queries,
)

requirements = parse_information_requirements(question, decomposition_output)
report = assess_context_sufficiency(
    requirements,
    [RequirementAssessment(
        requirement_id="account-plan",
        status=RequirementStatus.SUPPORTED,
        evidence_ids=("account/42@r9",),
    )],
)
queries = parse_retrieval_gap_queries(report, gap_query_output, maximum_queries=3)
```

| Status | Evidence rule | Retrieval consequence |
|---|---|---|
| Supported | At least one evidence ID | Requirement contributes to coverage |
| Contradicted | At least one evidence ID | Stop or resolve the conflict |
| Missing | No evidence required | May produce a bounded gap query |
| Ambiguous | Evidence optional | May produce a query that disambiguates |

An unassessed required item receives `Missing` status. Gap queries reference
open requirement IDs, including ambiguous ones. Resolved requirements stay
closed.

::: source-block
**Evidence**

[Google: sufficient context and agentic RAG](https://research.google/blog/unlocking-dependable-responses-with-gemini-enterprise-agent-platforms-agentic-rag/){.paper}[Self-RAG](https://arxiv.org/abs/2310.11511){.paper}[FLARE](https://arxiv.org/abs/2305.06983){.paper}
:::

## Measure which context helped

```{code-block} python
:caption: Record observed use and ablation evidence

from mari_components.retrieval import ContextUse, evaluate_context_contribution

contribution = evaluate_context_contribution(
    [
        ContextUse(item_id="plans@r7", token_count=200),
        ContextUse(item_id="history@r4", token_count=800),
    ],
    used_ids=["plans@r7"],
    observed_utility=0.80,
    ablated_utility={"plans@r7": 0.50},
)

assert contribution.utilization == 0.20
assert contribution.ablation_deltas["plans@r7"] == 0.30
```

Selected, cited, and causally useful are different claims. `used_ids` records
observable downstream use. Ablation deltas require a caller rerun that omits the
item. Mari reads them from the supplied measurements.

::: source-block
**Evidence**

[PlugMem: utility relative to consumed context](https://arxiv.org/abs/2603.03296){.paper}[Anthropic context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents){.paper}
:::

## Evaluate conditional disclosure separately from authorization

A disclosure condition describes when knowledge is relevant enough to reveal
or expand. Permission comes from application ACL filtering before or alongside
this predicate.

```{code-block} python
:caption: Evaluate an inspectable trigger over caller facts

from mari_components.retrieval import (
    DisclosureCondition, DisclosureOperator, DisclosureRule,
    evaluate_disclosure,
)

rule = DisclosureRule(
    rule_id="severe-incident-runbook",
    conditions=(
        DisclosureCondition(
            field="task_kind", operator=DisclosureOperator.EQUALS,
            value="incident",
        ),
        DisclosureCondition(
            field="severity", operator=DisclosureOperator.IN,
            value=("sev0", "sev1"),
        ),
    ),
)
decision = evaluate_disclosure(
    rule, {"task_kind": "incident", "severity": "sev1"}
)
```

| Operator | True when |
|---|---|
| `EXISTS` | Field is present, including a present `None` value |
| `EQUALS` | Present value equals the rule value |
| `NOT_EQUALS` | Field is present and differs |
| `IN` | Present value belongs to the rule's tuple, list, or set |

Rules can require all or any conditions and return every condition result.
Visibility, permission inspection, and retrieval execution belong to the application.

::: source-block
**Evidence**

[NIST attribute-based access control](https://doi.org/10.6028/NIST.SP.800-162){.paper}[Nocturne conditional disclosure implementation](https://github.com/Dataojitori/nocturne_memory){.paper}
:::

## Add context to chunks with source spans

`parse_chunk_context(document, section, model_output)` prepends a bounded
document-level explanation for indexing. The exact original
text, document and section revisions, and character offsets.
`pool_token_spans(token_embeddings, spans)` implements late-chunk mean pooling
over caller-tokenized half-open spans.

```{code-block} python
:caption: Index a contextual representation and cite the original

from mari_components.retrieval import parse_chunk_context

representation = parse_chunk_context(
    document,
    section,
    {"context": "This section defines enterprise account limits."},
    maximum_characters=400,
)

index.add(representation.indexing_text)
assert document.body[
    representation.evidence_start:representation.evidence_end
] == representation.original_text
```

| Representation | Context mechanism | Citation text |
|---|---|---|
| Contextual retrieval | Generated bounded prefix per chunk | Original section |
| Late chunking | Embed long text, pool token spans afterward | Original section |

::: source-block
**Evidence**

[Anthropic contextual retrieval](https://www.anthropic.com/news/contextual-retrieval){.paper}[Late Chunking](https://arxiv.org/abs/2409.04701){.paper}
:::

## Expand progressively from index to source

A `ProgressiveDisclosureManifest` connects small index entries to summaries,
sections, and full source units at the same artifact revision. The manifest
leaves unit generation and ranking to the caller.

```{code-block} python
:caption: Spend seven tokens on an index and summary before expanding to source

from mari_components.retrieval import (
    DisclosureLevel, DisclosureUnit, ProgressiveDisclosureManifest,
    expand_disclosure, inspect_disclosure_manifest,
)

manifest = ProgressiveDisclosureManifest(
    root_ids=("plans:index",),
    units=(
        DisclosureUnit(
            unit_id="plans:index", artifact_id="plans", revision="r7",
            level=DisclosureLevel.INDEX, text="Plan limits", token_count=2,
            expands_to=("plans:summary",),
        ),
        DisclosureUnit(
            unit_id="plans:summary", artifact_id="plans", revision="r7",
            level=DisclosureLevel.SUMMARY,
            text="Limits vary by plan.", token_count=5,
            expands_to=("plans:source",),
        ),
        DisclosureUnit(
            unit_id="plans:source", artifact_id="plans", revision="r7",
            level=DisclosureLevel.SOURCE,
            text=full_policy, token_count=600,
        ),
    ),
)

assert inspect_disclosure_manifest(manifest).valid
selection = expand_disclosure(manifest, token_budget=7)
assert [unit.unit_id for unit in selection.selected] == [
    "plans:index", "plans:summary",
]
```

| Manifest invariant | Reason |
|---|---|
| Unique unit IDs | Expansion targets are unambiguous |
| Same artifact and revision along an edge | Detail cannot silently cross versions |
| Strictly increasing level | Expansion always adds detail |
| No missing targets or cycles | Traversal is finite and inspectable |
| Explicit token counts | Every selected and skipped unit is budget-visible |

Expansion is breadth-first and caller-started. Authorization, relevance
ranking, and deciding whether more detail is needed remain separate steps.

::: source-block
**Evidence**

[MemWalker](https://arxiv.org/abs/2310.05029){.paper}[RAPTOR](https://arxiv.org/abs/2401.18059){.paper}[Pi LLM Wiki layered source and canonical pages](https://github.com/zosmaai/pi-llm-wiki){.paper}
:::

::: source-block
**Papers and implementations**

[Remember When It Matters](https://arxiv.org/abs/2607.08716){.paper}[Official proactive-memory implementation](https://github.com/yifannnwu/proactive-memory-agent){.paper}[PlugMem](https://www.microsoft.com/en-us/research/publication/plugmem-a-task-agnostic-plugin-memory-module-for-llm-agents/){.paper}[OpenAI Agents lifecycle hooks](https://openai.github.io/openai-agents-python/ref/lifecycle/){.paper}

[Mari generalizes the lifecycle seam. The host supplies the agent runtime and intervention policy.]{.small}
:::
