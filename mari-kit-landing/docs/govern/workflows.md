[]{#workflows}[Current]{.current-label}

# Reviewed workflows and cached answers

## Evaluation

Three end-to-end repository cases exercise workflow-step caching, selective invalidation after document drift, and rejection of stale or unauthorized dependencies. The tests validate exact reuse policy and provenance. They do not reproduce GPTCache hit-rate or task-quality measurements.

```console
$ pytest -q tests/test_examples.py tests/test_trajectories_agents.py -k 'workflow or cache'
7 passed
```

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


Reviewed workflow indexes match new requests to approved intents. Policy thresholds independently control speculative retrieval and direct cached-response reuse.

## How it works

Build an index from reviewed workflow intent vectors. At query time, compute normalized similarity, retain only workflows whose dependencies are authorized, and choose the best match with stable ties. Crossing the lower threshold may start retrieval speculatively; crossing the higher threshold only makes reuse eligible. A cached response is returned only after its exact evidence dependencies pass freshness checks. Similarity never overrides ACL or revision failure.

:::::::{container} diagram thresholds
<div>

**0.00**[run normally]{.small}

</div>

::: retr
**0.72**[start retrieval]{.small}
:::
