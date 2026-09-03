[]{#intent-mining}[Current]{.current-label}

# Intent mining

## At a glance

| Evaluation | Result | Interpretation |
|---|---:|---|
| Two cosmetic label variants across two runs | One aggregate with support `2` | Default grouping normalizes case, punctuation, and spacing |
| Out-of-range model evidence | `1/1` rejected | An intent cannot cite steps outside its source trajectory |
| Conflicting independent reviews | `1` valid, `1` invalid | Disagreement remains visible rather than becoming a verdict |
| Duplicate reviewer | `1/1` reported | Repeated output from one reviewer cannot manufacture support |
| Two-dimension rubric with required grounding omitted | Overall `0.800`; `1` missing and `1` required failure | The aggregate remains useful while the absent required dimension stays explicit |

These checks establish evidence and aggregation behavior. They do not measure
semantic intent accuracy: Mari never claims a model-generated label is correct
because it satisfies the schema.
Use a labeled domain corpus and independent reviewers to measure that semantic
accuracy for the model and taxonomy selected by the application.

## Represent an inferred intent

An `IntentCandidate` binds a label to one or more inclusive step ranges. Its
`kind` records whether the label was declared, inferred from behavior, or
proposed in hindsight from an unsuccessful run.

```{code-block} python
:caption: Validate intent labels proposed by any model

from mari_components.trajectories import parse_intent_candidates

candidates = parse_intent_candidates(
    runs,
    {
        "intents": [
            {
                "intent": "Compare retention policies",
                "kind": "inferred",
                "evidence": [
                    {"trajectory_id": "run-17", "start": 2, "end": 6}
                ],
            }
        ]
    },
)
```

| Field | Meaning |
|---|---|
| `intent` | Human-readable proposed intent, not a canonical ontology value |
| `kind` | `declared`, `inferred`, or `hindsight` |
| `evidence` | Existing trajectory ID and an inclusive, in-bounds step range |
| `actual_outcome` | What the run achieved; especially useful for hindsight proposals |
| `limitations` | What the cited behavior did not accomplish |
| `candidate_id` | Stable hash of kind, normalized label, and evidence ranges |

## Aggregate without choosing an ontology

`aggregate_intents(candidates, *, key=normalize_intent)` groups proposals and
returns all observed labels, candidate IDs, trajectory IDs, kinds, and support.
Replace `key` with a taxonomy lookup, embedding cluster assignment, or reviewed
mapping owned by the application.

```{code-block} python
:caption: Supply a reviewed grouping instead of accepting lexical identity

from mari_components.trajectories import aggregate_intents

groups = aggregate_intents(
    candidates,
    key=lambda label: reviewed_taxonomy[label],
)
```

## Cluster and monitor proposed intents

Before relabeling, applications can group semantically similar proposals with
caller-owned vectors. `cluster_intents` uses cosine-normalized single-link
clustering and returns each cluster's medoid, cohesion, labels, members, and
ambiguous members. `detect_novel_intents` measures each proposal against
caller-owned centroids. `compare_intent_windows` compares reviewed cluster
matches with Jensen–Shannon divergence and explicit new or retired clusters.

```{code-block} python
:caption: Discover intent families without making them Mari's ontology

from mari_components.trajectories import cluster_intents, detect_novel_intents

clustering = cluster_intents(
    candidates,
    embeddings,
    similarity_threshold=0.82,
    ambiguity_margin=0.03,
)
novel = detect_novel_intents(
    new_candidates,
    new_embeddings,
    reviewed_centroids,
    threshold=0.75,
)
```

| Three-label vector example | Cosine relationship | Result |
|---|---:|---|
| “reset password” / “recover login” | `0.9999` | Same cluster at `0.90` |
| “reset password” / “cancel account” | `0.0000` | Separate cluster |

Single-link clustering can bridge distant members through intermediate points;
cohesion and ambiguous IDs make that failure mode inspectable. Cluster matching
across time is caller-supplied because Mari does not invent stable taxonomy IDs.

::: source-block
**Evidence**

[Google: intent extraction through decomposition](https://research.google/blog/small-models-big-results-achieving-superior-intent-extraction-through-decomposition/){.paper}[EMNLP 2025 intent decomposition paper](https://aclanthology.org/2025.emnlp-main.949/){.paper}[Jensen–Shannon divergence](https://doi.org/10.1109/18.61115){.paper}
:::

## Relabel outcomes in hindsight

A failed run may still demonstrate a different achieved intent. Record that as
`kind="hindsight"`, retain the original failure elsewhere, and cite the steps
that support the proposed alternative. Mari does not rewrite the source run or
package it as training data.

```{code-block} python
:caption: Keep independent semantic reviews separate from schema validation

from mari_components.trajectories import IntentReview, summarize_intent_reviews

reviews = summarize_intent_reviews(
    candidates,
    [
        IntentReview(candidate_id=candidate_id, reviewer_id="judge-a", valid=True),
        IntentReview(candidate_id=candidate_id, reviewer_id="judge-b", valid=False),
    ],
)

assert reviews[0].agreement == 0.5
```

`summarize_intent_reviews(candidates, reviews)` deduplicates reviewer identity
and reports valid, invalid, and duplicate counts. It intentionally has no
acceptance threshold.

## Task-adaptive evaluation dimensions

Intent labels describe what behavior was trying to accomplish; a rubric
describes what matters when judging that behavior. The two values remain
separate.

```{code-block} python
:caption: Generate elsewhere, validate and score here

from mari_components.trajectories import (
    parse_rubric_assessments,
    parse_trajectory_rubric,
    score_trajectory_rubric,
)

rubric = parse_trajectory_rubric(task, rubric_output)
assessments = parse_rubric_assessments(run, rubric, judge_output)
score = score_trajectory_rubric(
    run,
    rubric,
    assessments,
    required_minimum=0.7,
)

print(score.overall, score.required_failures, score.missing_dimensions)
```

| Function | Options and behavior |
|---|---|
| `parse_trajectory_rubric(task, model_output)` | Requires unique dimensions with positive weights; preserves `required` dimensions |
| `parse_rubric_assessments(run, rubric, model_output)` | Accepts scores/confidence in `[0,1]`; validates every evidence-step index |
| `score_trajectory_rubric(..., required_minimum=0.5)` | Confidence-weights repeated assessments; reports missing and required failures separately from the weighted mean |

The separate `required_failures` field prevents a high score on easy
dimensions from hiding a missing grounding or safety dimension. The caller
still decides whether any score or failure changes behavior.

:::{collapse} One scored rubric, as data

| Dimension | Weight | Required | Assessment | Result |
|---|---:|---:|---:|---|
| Grounding | `2` | yes | missing | Listed in both `missing_dimensions` and `required_failures` |
| Efficiency | `1` | no | `0.800` at confidence `0.750` | Included in the weighted mean |
| Overall | — | — | — | `0.800` over assessed dimensions; not presented as a passing verdict |
:::

::: source-block
**Research and implementations**

[AgentHER](https://arxiv.org/abs/2603.21357){.paper}[Apache-2.0 implementation](https://github.com/alphadl/AgentHER){.paper}[Hindsight Supervised Learning](https://arxiv.org/abs/2607.04235){.paper}[AdaRubric](https://arxiv.org/abs/2603.21362){.paper}[Apache-2.0 implementation](https://github.com/alphadl/AdaRubrics){.paper}[Hindsight Experience Replay](https://arxiv.org/abs/1707.01495){.paper}

[Mari implements evidence-bound proposals, independent review summaries, and rubric arithmetic. It does not implement their training pipelines or model judges.]{.small}
:::
