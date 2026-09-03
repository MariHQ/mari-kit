[]{#memory-algorithms}[Current]{.current-label}

# Memory segmentation and mutation plans

## Evaluation

Four algorithm cases cover add/update/delete/no-op mutation plans, conflicting-target rejection, the joint attention-peak/similarity-valley segmentation rule, and non-splitting counterexamples. The cleaned LongMemEval-S retrieval baseline separately scores session retrieval at `0.8298` Recall-all@5 and `0.9021` Recall-all@10 over 470 questions. Mutation F1 and segmentation boundary F1 have not yet been measured.

```console
$ pytest -q tests/test_memory_algorithms.py
$ python benchmarks/run_public.py longmemeval
4 passed
```


`hybrid_topic_segments` splits a stream only where an attention-boundary peak and a semantic-similarity valley agree. The application extracts candidates from those bounded groups and classifies each one as add, update, delete, or no-op. `plan_memory_mutations` validates the decisions without writing storage.

## How it works

Normalize boundary and adjacent-similarity arrays to the `n−1` gaps between `n` turns. A gap is eligible only when its attention score is a local peak above the configured boundary threshold and its adjacent semantic similarity is below the valley threshold. Eligible gaps split consecutive, non-overlapping segments. Mutation planning then requires exactly one decision per candidate, validates update/delete targets against current IDs, rejects duplicate adds and conflicting operations on one target, and returns a deterministic plan.

::::::{container} diagram promotion
<div>

**Turns**[attention + similarity signals]{.small}

</div>

*topic boundary*

<div>

**Candidate memories**[host extraction and classification]{.small}

</div>

*validated plan*

<div>

**Host commit**[ADD · UPDATE · DELETE · NOOP]{.small}

</div>
::::::

```{code-block} python
:caption: memory_update.py

from mari_components.knowledge import (
    MemoryDecision, MemoryOperation, hybrid_topic_segments,
    plan_memory_mutations,
)

segments = hybrid_topic_segments(turns,
    attention_boundaries=attention, adjacent_similarities=similarity,
    similarity_threshold=0.40)

plan = plan_memory_mutations(existing, candidates, {
    "new-role": MemoryDecision(operation=MemoryOperation.UPDATE,
        target_id="role", reason="newer explicit statement"),
    "unchanged": MemoryDecision(operation=MemoryOperation.NOOP),
})
store.commit(plan, expected_generation=generation)
```

**Classification remains application-owned.**Mari checks candidate coverage, target existence, add collisions, and conflicting target operations. `apply_memory_mutations` provides a pure preview for tests; it is not a database.

::: source-block
**Research basis**

[Mem0: memory extraction and update operations](https://arxiv.org/abs/2504.19413){.paper}[LightMem: topic-aware memory consolidation](https://arxiv.org/abs/2510.18866){.paper}

[The conjunctive peak/valley rule and mutation validation are Mari implementations; model-based classification remains outside the library.]{.small}
:::
