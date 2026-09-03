[]{#link-prediction}[Current]{.current-label}

# Structural link candidates

## At a glance

For neighborhoods Γ(u) and Γ(v):

| Score | Calculation | Tendency |
|---|---|---|
| Common neighbors | `|Γ(u) ∩ Γ(v)|` | Favors many shared neighbors |
| Jaccard | Intersection divided by union | Normalizes neighborhood size |
| Adamic--Adar | Sum of `1 / log(degree(w))` | Gives rare shared neighbors more weight |
| SimRank | Recursive similarity of incoming neighborhoods | Finds structurally similar nodes without a shared immediate neighbor |

## How it works

These functions score candidate pairs supplied by the caller. Mari does not generate edges or assume that a high score means a relationship exists. Direction, edge types, temporal filtering, and authorization are expressed by the `neighbors` callback.

```{code-block} python
:caption: Rank only application-approved candidate pairs

from mari_components.graph import score_link_candidates

scores = score_link_candidates(
    candidate_pairs=(("alice", "project-x"), ("alice", "project-y")),
    neighbors=authorized_neighbors,
    method="adamic_adar",
)

for candidate in scores:
    if candidate.score >= review_threshold:
        review_queue.add(candidate)
```

`simrank_scores` is available separately because it scores all pairs in a bounded node set and iterates over incoming-neighbor similarity. It is substantially more expensive than local scores.

## What to evaluate

| Split | Measure |
|---|---|
| Held-out observed links | Hits@k, MRR, ROC-AUC, average precision |
| Time-based split | Future-link precision without temporal leakage |
| Candidate generator | Recall before structural scoring |
| Degree slices | Performance for sparse and hub nodes separately |

::: source-block
**Papers and implementations**

[Link prediction problem](https://doi.org/10.1002/asi.20591){.paper}[Adamic--Adar](https://doi.org/10.1016/S0378-8733(03)00009-1){.paper}[SimRank](https://doi.org/10.1145/775047.775126){.paper}[NetworkX link prediction](https://networkx.org/documentation/stable/reference/algorithms/link_prediction.html){.paper}

[Scores are topology-only evidence and should not be presented as semantic facts.]{.small}
:::
