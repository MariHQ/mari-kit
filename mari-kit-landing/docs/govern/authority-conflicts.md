[]{#authority-conflicts}[Supported]{.current-label}

# Source authority, conflicts, and uncertainty

## Contract

| Assertion | Source policy | Valid time | Working result |
|---|---:|---|---|
| Headquarters is Oakland | Company blog: 0.65 | 2024 onward | Preserved as dissenting evidence |
| Headquarters is San Francisco | Regulatory filing: 0.95 | 2025 onward | Selected for the current answer |
| Headquarters was Oakland | Regulatory filing: 0.95 | Until 2025 | Retained as historically valid |

The result contains a working selection, alternatives, grouped scores, and a
dispute flag. Retain the source assertions and a versioned policy alongside
the result for audit.

## How it works

Select one entity's assertions before calling the resolver. It requires one
predicate and optionally filters half-open validity intervals at `at_time`.
It groups equal value representations, sums source weight × confidence ×
independence, and adds a bonus for distinct source kinds. A margin below
`minimum_margin` sets `disputed=True` and leaves `selected=None`.

```{code-block} python
:caption: Resolve a claim and preserve disagreement

from mari_components.governance import AuthorityPolicy, SourceAssertion, resolve_assertions

result = resolve_assertions(
    assertions=(filing_assertion, blog_assertion),
    policy=AuthorityPolicy(
        source_weights={"regulatory_filing": 0.95, "company_blog": 0.65},
        corroboration_weight=0.15,
        minimum_margin=0.10,
    ),
)

if result.disputed:
    answer = "The available sources disagree."
else:
    answer = result.selected.value
```

Source weights and independence estimates belong to the application. Pass
`at_time` explicitly for current or historical answers. Omitting it admits
assertions from every validity interval. Observation and extraction provenance
belong in the surrounding [knowledge artifact](../platform/artifacts.md).

## Measures

| Evaluation | Measure |
|---|---|
| Synthetic conflicts with known authority | Selected-value accuracy |
| Equal-quality disagreement | Dispute calibration and forced-answer rate |
| Temporally changing facts | Correct value at requested valid time |
| Correlated sources | False corroboration caused by copied reporting |

::: source-block
**Papers and standards**

[Truth discovery survey](https://doi.org/10.1145/2896813){.paper}[Uncertainty in knowledge-graph construction](https://doi.org/10.4230/TGDK.3.1.3){.paper}[Knowledge Vault](https://dl.acm.org/doi/10.1145/2623330.2623623){.paper}[W3C PROV](https://www.w3.org/TR/prov-overview/){.paper}

[Mari implements an explainable deterministic resolver. Learned source-quality estimation remains application supplied.]{.small}
:::
