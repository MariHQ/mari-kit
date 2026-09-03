[]{#workflows}[Current]{.current-label}

# Reviewed workflows and cached answers

## Contract

| Match state | Reuse decision |
|---|---|
| Similar, reviewed, authorized, and fresh | Reuse cached answer or procedure |
| Similar and stale | Retrieve and recompute |
| Similar and outside allowed documents | Ignore before scoring |
| Below similarity threshold | Run the normal workflow |

Cache quality depends on caller-provided query vectors and the threshold. Mari places authorization and freshness checks on the decision path.


:::{collapse} Example cache decisions

| Similarity | Dependencies | Review state | Decision |
|---:|---|---|---|
| Above threshold | Fresh and readable | Approved | Reuse |
| Above threshold | Stale | Approved | Reject |
| Above threshold | Unauthorized | Approved | Reject |
| Highest score | Fresh | Unreviewed | Reject. Consider lower approved match |
:::

:::::::{container} diagram thresholds
<div>

**0.00**[run normally]{.small}

</div>

::: retr
**0.72**[start retrieval]{.small}
:::

::: reuse
**0.95**[consider reuse]{.small}
:::

<div>

**1.00**

</div>
:::::::

```{code-block} python
:caption: workflow.py

from mari_components.trajectories import (
    WorkflowPolicy, build_reviewed_workflow_index, decide_reviewed_workflow,
)

index = build_reviewed_workflow_index(reviewed_workflows)
decision = decide_reviewed_workflow(query_vectors, index, current_revisions,
    policy=WorkflowPolicy(speculation_threshold=0.72, cache_threshold=0.95),
    allowed_document_ids=authorized_document_ids)
```

Related APIs: `match_reviewed_workflow`, `start_speculative_retrieval`, `match_cached_response`, and `workflow_freshness`. Reuse requires a strong match plus fresh, authorized dependencies.

::: source-block
**Research basis**

[GPTCache: semantic caching for language-model queries](https://aclanthology.org/2023.nlposs-1.24/){.paper}[Build Systems à la Carte: dependency-valid reuse](https://www.microsoft.com/en-us/research/wp-content/uploads/2018/03/build-systems.pdf){.paper}

[The two thresholds, authorization gate, and exact freshness condition are Mari policy.]{.small}
:::


Reviewed workflow indexes match new requests to approved intents. Separate policy thresholds control speculative retrieval and direct cached-response reuse.

## How it works

Build an index from reviewed workflow intent vectors. At query time, compute
normalized similarity and filter workflows by dependency authorization. Choose
the best match with stable ties. The lower threshold makes speculative
retrieval eligible. The higher threshold makes reuse eligible. A cached
response requires fresh exact evidence dependencies. ACL and revision checks
govern the final decision.
