[]{#architecture}

# Architecture

## At a glance

| Mari owns | Application owns |
|---|---|
| Immutable types, deterministic policies, traces, and metrics | Models, agent loop, scheduling, credentials, and authorization decisions |
| Connector and store protocols | HTTP transports and production database transactions |
| Reference in-memory algorithms | Capacity planning and distributed operations |


:::{collapse} Worked ownership boundary

| Mari owns | Application owns |
|---|---|
| Immutable types and pure planning | Agent loop and scheduling |
| Connector protocol and normalized pages | Credentials and HTTP transport |
| Store protocol and reference semantics | Production database transactions |
| Evaluation metrics and run identity | Model invocation and deployment |
:::

:::::::{container} diagram flow
::: card
**Sources**[provider APIs]{.small}
:::

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

Provider data is normalized into immutable values. Pure functions transform those values into plans, candidates, reports, or index payloads. The caller validates the return value and commits it through its own transaction boundary. Because network and storage operations are injected, the same input values can be inspected or dry-run before any side effect occurs.

::: source-block
**Research and standards**

[W3C PROV data model](https://www.w3.org/TR/prov-dm/){.paper}[Data pipeline reproducibility](https://arxiv.org/abs/2006.12117){.paper}

[Provenance and reproducibility motivate explicit entities, revisions, activities, and captured configuration. The pure-planning/application-commit split is a Mari engineering contract.]{.small}
:::


Values cross explicit boundaries. Mari plans and validates; the application performs side effects.

```{code-block} python
:caption: Keep model and persistence calls outside the domain layer

from mari_components import KnowledgeDocument
from mari_components.knowledge import document_sections, parse_facts

document = KnowledgeDocument(
    source_id="handbook",
    external_id="refunds",
    title="Refund policy",
    body="Enterprise refunds close after 30 days.",
    revision="sha256:8f31c2a",
)
sections = document_sections(document)

# The application invokes its model. Mari accepts only evidence that resolves
# against the exact document revision supplied here.
model_output = call_model(document, sections)
facts = parse_facts([document], model_output)
artifact_store.commit(facts)
```
