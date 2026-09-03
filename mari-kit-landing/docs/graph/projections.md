[]{#projections}[Current]{.current-label}

# Event sourcing and disposable projections

```{include} ../_includes/eval/graph.md
```

Canonical artifacts and append-only events remain authoritative. `replay_projection` builds deterministic derived state and gives each build a content identity. A backend can validate and swap that build using its own transaction boundary.

## How it works

Events must have unique IDs and contiguous generations. The replay function folds them in order and hashes the complete event input. Generation gaps and duplicate events fail before a usable build is returned. Storage adapters own staging validation, pointer swaps, and rollback because those guarantees depend on the selected database.

::: source-block
**Papers and standards**

[Data pipeline reproducibility](https://arxiv.org/abs/2006.12117){.paper}[Invariant confluence](https://arxiv.org/abs/1402.2237){.paper}[W3C PROV](https://www.w3.org/TR/prov-overview/){.paper}
:::

::::::{container} diagram projection-flow
<div>

**Canonical artifacts**[documents · events · reviews]{.small}

</div>

*deterministic fold*

<div>

**Staging projections**[vector · lexical · graph · Markdown]{.small}

</div>

*validate + swap*

<div>

**Current read version**[rollback pointer retained]{.small}

</div>
::::::

```{code-block} python
:caption: Deterministic replay with contiguous generations

from mari_components.platform import KnowledgeEvent, replay_projection

events = [
    KnowledgeEvent(
        event_id="event-1",
        generation=1,
        kind="artifact.indexed",
        payload={"artifact_id": "policy-7"},
    )
]

def project(state: set[str], event: KnowledgeEvent) -> set[str]:
    return state | {str(event.payload["artifact_id"])}

build = replay_projection(set(), events, projector=project)
assert build.state == {"policy-7"}
assert build.generation == 1
print(build.build_id)  # stable SHA-256 identity of the replay input
```
