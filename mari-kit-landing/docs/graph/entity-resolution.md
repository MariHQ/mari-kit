[]{#entity-resolution}[Current]{.current-label}

# Entity resolution with explicit uncertainty

## Behavior

| WDC held-out result | Value | Decision implication |
|---|---:|---|
| Pair precision | `0.623` | Roughly four in ten automatic links were wrong |
| Pair recall | `0.507` | About half of true matches were linked |
| Pair F1 | `0.559` | URL fields produced too many errors for unattended merging |
| Review rate | `0.476` | The review band sends uncertain pairs to review |

The run uses URLs from the compact WDC gold files. Product titles and
identifiers belong in the next field-evidence run. Attributes provide another
signal to measure there.

:::{collapse} Example resolution trace

| Feature | Agrees | Match probability | Non-match probability | Contribution |
|---|---:|---:|---:|---:|
| Email | Yes | 0.99 | 0.01 | Positive log-likelihood |
| Name | No | 0.90 | 0.20 | Negative log-likelihood |

The summed score is compared with separate link and review thresholds. Ambiguous records remain review candidates.
:::



The cascade spends expensive work after cheap deterministic checks. Ambiguous candidates enter a merge through a configured threshold or a review decision.

## How it works

Block candidates by tenant, scope, and entity type. Compare normalized exact aliases. Calculate field-agreement and fuzzy scores. Retrieve a small embedding neighborhood for unresolved candidates. Then apply separate link and review thresholds. Scores above link become a proposed canonical ID, scores in the review band retain all candidates and their feature trace, and lower scores remain distinct entities.

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
