[]{#architecture}

# Architecture

## Evaluation

Five architecture tests inspect the package boundary: one distribution, no agent loop, no application container, no environment/process discovery, and no host-framework or storage imports in the core. Four platform cases separately evaluate pipeline, projection, compiler, and store boundaries.

```console
$ pytest -q tests/test_architecture.py tests/test_platform.py
9 passed
```

*poll*

::: card
**Documents**[identity · revision · ACL]{.small}
:::

*derive*

::: card
**Knowledge**[facts · answers · decisions]{.small}
:::

*retrieve*

::: card
**Context**[allowed · fresh · cited]{.small}
:::
:::::::

| Mari supplies | Application supplies |
|----|----|
| Typed values and pure planning functions | Database and transactions |
| Connector polling and cursor contracts | Credentials, HTTP transport, retries, scheduler |
| Strict parsers for generated values | Model, prompts, and inference |
| Retrieval and index serialization | Embeddings and index lifecycle |
| Policy and evaluation functions | Authorization and agent runtime |

## How it works

Provider data is normalized into immutable values. Pure functions transform those values into plans, candidates, reports, or index payloads. The caller validates the return value and commits it through its own transaction boundary. Because network and storage operations are injected, the same input values can be replayed in tests before any side effect occurs.

::: source-block
**Research and standards**

[W3C PROV data model](https://www.w3.org/TR/prov-dm/){.paper}[Data pipeline reproducibility](https://arxiv.org/abs/2006.12117){.paper}

[Provenance and reproducibility motivate explicit entities, revisions, activities, and captured configuration. The pure-planning/application-commit split is a Mari engineering contract.]{.small}
:::


Values cross explicit boundaries. Mari plans and validates; the application performs side effects.

:::::::{container} diagram flow
::: card
**Sources**[provider APIs]{.small}
:::
