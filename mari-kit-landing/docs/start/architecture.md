[]{#architecture}

# Architecture

## Ownership

| Component | Supplied by |
|---|---|
| Immutable types, deterministic policy functions, traces, and metrics | Mari |
| Connector protocols and store protocols | Mari |
| Reference in-memory algorithms | Mari |
| Models, agent loop, scheduler, credentials, and authorization decisions | Application |
| HTTP transport and production database transactions | Application |
| Capacity planning and distributed operations | Application |

The application defines its knowledge graph. Mari's graph tools accept its IDs,
iterables, and callbacks. Functions return data for inspection. The application
chooses storage writes and the next operation.


:::{collapse} Ownership example

| Work | Supplied by |
|---|---|
| Immutable types and pure planning | Mari |
| Connector protocol and normalized pages | Mari |
| Store protocol and reference semantics | Mari |
| Evaluation metrics and run identity | Mari |
| Agent loop and scheduling | Application |
| Credentials and HTTP transport | Application |
| Production database transactions | Application |
| Model invocation and deployment | Application |
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

| Component | Provider |
|---|---|
| Typed values and pure planning functions | Mari |
| Connector polling and cursor contracts | Mari |
| Strict parsers for generated values | Mari |
| Retrieval and index serialization | Mari |
| Policy functions and evaluation functions | Mari |
| Database and transactions | Application |
| Credentials, HTTP transport, retries, and scheduler | Application |
| Model, prompts, and inference | Application |
| Embeddings and index lifecycle | Application |
| Authorization and agent runtime | Application |

| Application-defined concept | Why it stays with the application |
|---|---|
| Node, edge, statement, and ontology semantics | Every knowledge system has its own identity rules |
| Graph construction order | The current task determines how tools compose |
| Query language and planner | Storage capabilities shape query costs |
| Merge, promotion, and truth policy | The caller assigns consequences to Mari's proposals |
| Graph runtime and transaction manager | The data layer controls persistence and isolation |

## How it works

Provider data enters Mari as immutable values. Pure functions produce plans,
candidates, reports, or index payloads. The caller inspects a result, then sends
approved writes through its transaction boundary. Injected network and storage
functions also let the caller run the same inputs in a dry run.

::: source-block
**Research and standards**

[W3C PROV data model](https://www.w3.org/TR/prov-dm/){.paper}[Data pipeline reproducibility](https://arxiv.org/abs/2006.12117){.paper}

[Provenance work motivates explicit entities and immutable revisions. Mari also
records the activity and configuration that produced a value. Its API contract
places planning in library functions and commits in application code.]{.small}
:::

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

# The application invokes its model. Mari requires evidence that resolves
# against the exact document revision supplied here.
model_output = call_model(document, sections)
facts = parse_facts([document], model_output)
for fact in facts:
    proposal_queue.append(fact)
```
