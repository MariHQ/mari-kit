[]{#entity-resolution}[Reference]{.current-label}

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

The caller assembles the cascade: block by tenant, scope, and entity type,
compare normalized aliases, and optionally add fuzzy or embedding candidates.
`resolve_entity` scores one supplied field-agreement comparison. It returns
`LINK`, `REVIEW`, or `DISTINCT` and each field's contribution. Canonical-ID
selection and merging remain separate caller decisions.

Scores sum natural-log likelihood ratios. They are comparison scores, distinct
from calibrated match probabilities. Estimate field probabilities on labeled
matches and distinct pairs, then select thresholds for your tolerated merge
error. Correlated fields can repeat the same evidence. Inspect their individual
contributions and the resulting review volume.

::: source-block
**Papers**

[Fellegi--Sunter: probabilistic record linkage](https://doi.org/10.1080/01621459.1969.10501049){.paper}
:::

:::{container} diagram resolution-cascade
[scope + type block]{.step} [normalized exact]{.step} [field/fuzzy score]{.step} [embedding candidates]{.step} [link · reject · review]{.step}
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
