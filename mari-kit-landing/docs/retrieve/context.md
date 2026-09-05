[]{#context}[Supported]{.current-label}

# Retrieval plans and context envelopes

## Behavior

| QASPER packing configuration | Observed result | Meaning |
|---|---:|---|
| 1,024-token, 12-document budget | Evidence recall `0.527` | About half of annotated evidence survived packing |
| Same run | Evidence density `0.117` | Context occupied most packed tokens. Annotated evidence occupied the remainder |
| Authorization filter | Leakage `0` | Unauthorized candidates are removed before ordering and rendering |

The first two values describe this BM25-backed configuration. Adjust budget and
ranking together. Evaluate freshness and ordering as separate dimensions.

| Consumer probe | Evidence coverage | Other dimension | Decision consequence |
|---|---:|---:|---|
| Temporal research context | `1.000` | Temporal precision `0.667` | Perfect evidence recall admitted a historical assertion |
| Code evidence retrieval | Recall `1.000` | MRR `0.500` | All relevant files appeared. The first result was wrong |
| Literature context, raw | Precision/recall `0.500` | NDCG `0.613` | Two manifestations of one study hid an independent contradiction |
| Literature context, group-constrained | Precision/recall `1.000` | NDCG `1.000` | One manifestation per caller-defined study group preserved both stances |

:::{collapse} Example inclusion trace

| Candidate | Authorized | Fresh | Fits budget | Decision |
|---|---:|---:|---:|---|
| `policy-current` | Yes | Yes | Yes | Included |
| `policy-stale` | Yes | No | Yes | Excluded: stale revision |
| `private-note` | No | Yes | Yes | Excluded before scoring |
| `appendix` | Yes | Yes | No | Excluded: token budget |
:::



Mari packs already-ranked retrieval candidates into a bounded, revision-bearing context envelope. Its trace explains every inclusion and exclusion.

## How it works

Run semantic, lexical, graph, and recency arms over authorized IDs. Convert arm scores to ranks and combine them with reciprocal-rank fusion, then discard stale dependencies, rerank survivors, diversify near-duplicates, and greedily pack whole evidence excerpts under token/document limits. The envelope contains rendered context plus source revisions and per-candidate include/exclude reasons, allowing the caller to reproduce what the model saw.

**Research basis**[RAG](https://arxiv.org/abs/2005.11401){.paper} motivates explicit, updateable non-parametric memory and provenance. [RAG-Fusion](https://arxiv.org/abs/2402.03367){.paper} and [MMR](https://www.cs.cmu.edu/afs/cs/Web/People/jgc/publication/MMR_DiversityBased_Reranking_SIGIR_1998.pdf){.paper} back fusion and diversity. [Lost in the Middle](https://arxiv.org/abs/2307.03172){.paper} makes budget and evidence order evaluation requirements. `ContextEnvelope` is Mari\'s carrier for those observable decisions.

::::::{container} diagram context
::: arms
semantic

lexical

graph

recent
:::

*RRF*

::: stage
**authorize**

**freshness**

**rerank**
:::

*budget*

<div>

**ContextEnvelope**[excerpts · evidence · revisions · trace]{.small}

</div>
::::::

```{code-block} python
:caption: context.py

from mari_components.retrieval import ContextBudget, ContextCandidate, assemble_context

context = assemble_context([
    ContextCandidate(document_id=hit.document_id, revision=revisions[hit.document_id],
        text=passages[hit.document_id], token_count=token_count(hit.document_id),
        score=hit.score, authorized=can_read(hit.document_id),
        fresh=is_fresh(hit.document_id))
    for hit in fused_hits
], budget=ContextBudget(tokens=6000, documents=12))

model(context.text)
audit(context.trace)
```

## Artifact-neutral composition

`hydrate_hits` preserves rank, score, misses, and resolver failures. It
joins index IDs to revisioned `RetrievalUnit` values. `select_context` then
packs those units under any set of caller-named budgets. The selection trace
retains every eligibility or budget rejection.

```{code-block} python
:caption: Hydrate ranked units and apply token and latency budgets

from mari_components.retrieval import (
    ContextItem, hydrate_hits, select_context,
)

hydrated = hydrate_hits(
    hits,
    identity=lambda hit: hit.document_id,
    score=lambda hit: hit.score,
    resolve=unit_store.get,
)

selection = select_context(
    [ContextItem(
        unit=hit.unit,
        score=hit.score,
        costs={"tokens": count_tokens(hit.unit.text), "latency_ms": 2},
        eligible=valid_at_query_time(hit.unit),
        exclusion_reasons=() if valid_at_query_time(hit.unit) else ("historical",),
    ) for hit in hydrated if hit.unit is not None],
    limits={"tokens": 6000, "latency_ms": 30},
)

model(selection.render())
validate_answer(visible_refs=selection.visible_refs)
```

The greedy packer is an inspectable reference algorithm. Token, byte, latency,
and monetary costs have caller-defined names, limits, and priority.

Build atom-backed units with `RetrievalUnit.from_atom(atom, source=source)`.
Its reference matches `atom.to_revision_ref(source=source)` after conversion
through `unit.ref.to_revision_ref()`. This preserves one identity from
[semantic atoms](../ingest/semantic-atoms.md) to visible context and
[citation validation](../govern/evidence.md). Compute authorization and
freshness before setting each item's `eligible` value.

## Constraint and diversity selection

`select_context_diverse` adds caller-defined group caps, minimum group
coverage, and a marginal-gain callback. The algorithm greedily chooses the
largest feasible marginal gain, prioritizing unsatisfied required groups. It
returns selection order, group counts, selected gains, final-set counterfactual
gains for excluded candidates, budget failures, group cap failures, and
infeasible minimums.

`rounds` records the feasible candidates and gains at each greedy iteration,
the groups unmet at that moment, the selected ref, and an explicit
`below_minimum_gain` or `no_feasible_candidate` stop. The compact `trace`
separately describes each candidate against the final selected set.

```{code-block} python
:caption: Keep independent evidence families in a two-item context

from mari_components.retrieval import select_context_diverse

selection = select_context_diverse(
    candidates,
    limits={"items": 2, "tokens": 1200},
    groups=lambda item: (item.unit.metadata["study_id"],),
    maximum_per_group={study_id: 1 for study_id in study_ids},
    minimum_per_group={"trial-b": 1, "trial-c": 1},
    marginal_gain=lambda item, selected: evidence_gain(item, selected),
)
```

The selector is a constrained greedy baseline. Monotone submodular objectives have
established approximation results for greedy maximization. Caller gain
functions determine whether those results apply.
[Submodular maximization](https://doi.org/10.1007/BF01588971){.paper}

`evaluate_grouped_coverage` reports per-group recall, represented-group
fraction, and duplicate-group redundancy. These use fields apart from item-level
precision and relevance.

```{code-block} python
:caption: Detect a context containing two versions of one study

from mari_components.evaluation import evaluate_grouped_coverage

coverage = evaluate_grouped_coverage(
    selected_ids,
    expected_ids,
    group=lambda paper_id: study_family[paper_id],
)
print(coverage.represented_group_fraction, coverage.redundancy_rate)
```

## Cross-stage decisions

`filter_with_reasons` evaluates all caller predicates and retains every failed
reason. `CandidateHistory` appends decisions from graph selection, projection,
retrieval, reranking, and context packing. The final audit exposes attrition at
each stage.

```{code-block} python
:caption: Preserve an expired-item rejection before retrieval

from mari_components.retrieval import (
    CandidateHistory, FilterPredicate, decisions_from_context,
    decisions_from_filter, filter_with_reasons,
)

applicable = filter_with_reasons(clauses, predicates=(
    FilterPredicate(reason="expired", accepts=is_current),
    FilterPredicate(reason="wrong_jurisdiction", accepts=in_scope),
))

hits = index.search(query, allowed_refs={clause.ref for clause in applicable.accepted})

history = CandidateHistory().append(
    *decisions_from_filter(
        applicable, stage="applicability", identity=lambda clause: clause.ref,
    ),
    *decisions_from_context(selection, stage="context"),
)
```

The adapters copy values into a common append-only trace. Stage order, algorithm
invocation, and workflow remain caller decisions.

`diagnose_candidate_history` checks for conflicting decisions at the same
stage, missing parents, and multiple raw IDs that map to one caller-defined
canonical identity. Pass `canonicalize=` explicitly when stages use different
identifier representations. Mari uses the caller's explicit canonicalization.
