[]{#entity-resolution}[Current]{.current-label}

# Entity resolution with explicit uncertainty

## Evaluation

| Evaluation | Cases | Result | Corpus result |
|---|---:|---:|---|
| Fellegi--Sunter contributions and thresholds | 1 | 1 / 1 pass | — |
| WDC Products resolution | — | Not run | Pair/cluster F1 unavailable |

:::{collapse} Worked resolution trace

| Feature | Agrees | Match probability | Non-match probability | Contribution |
|---|---:|---:|---:|---:|
| Email | Yes | 0.99 | 0.01 | Positive log-likelihood |
| Name | No | 0.90 | 0.20 | Negative log-likelihood |

The summed score is compared with separate link and review thresholds; ambiguous records remain review candidates.
:::

### Reproduce

```console
$ pytest -q tests/test_graph_foundations.py -k fellegi
```


The cascade spends expensive work only after cheap deterministic checks. It never converts an ambiguous candidate into a merge without a configured threshold or review decision.

## How it works

Block candidates by tenant, scope, and entity type; compare normalized exact aliases; calculate field-agreement and fuzzy scores; retrieve a small embedding neighborhood only for unresolved candidates; then apply separate link and review thresholds. Scores above link become a proposed canonical ID, scores in the review band retain all candidates and their feature trace, and lower scores remain distinct entities.

::: source-block
**Papers**

[Fellegi--Sunter: probabilistic record linkage](https://doi.org/10.1080/01621459.1969.10501049){.paper}
:::

:::{container} diagram resolution-cascade
scope + type block*→*normalized exact*→*field/fuzzy score*→*embedding candidates*→*link · reject · review
:::

```{code-block} python
:caption: resolution.py

from mari_components.graph import FieldAgreement, ResolutionDecision, resolve_entity

resolution = resolve_entity([
    FieldAgreement(field="email", agrees=True,
        match_probability=0.99, nonmatch_probability=0.01),
    FieldAgreement(field="name", agrees=False,
        match_probability=0.90, nonmatch_probability=0.20),
], link_threshold=4.0, review_threshold=1.0)

if resolution.decision is ResolutionDecision.REVIEW:
    review_queue.put(candidate, resolution.contributions)
```
