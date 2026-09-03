[]{#memory-algorithms}[Current]{.current-label}

# Memory segmentation and mutation plans

## Behavior

| Mechanism | Observed behavior | What remains application-owned |
|---|---|---|
| Mem0 mutation plan | 500 LongMemEval evidence replays preserved the latest value. 448 updates | The model that labels add, update, delete, or no-op |
| LightMem segmentation | WikiSection boundary F1 `0.237` with lexical novelty signals | Attention and semantic-similarity models |
| Salience ranking | LongMemEval complete evidence recall@10 `0.906` | Importance and relevance scores |

The replay number validates mutation execution. Mutation classification remains a separate concern. The segmentation score shows that a naive lexical signal is a baseline for production use.

:::{collapse} Example mutation and segmentation examples

| Existing memory | New observation | Planned operation |
|---|---|---|
| No matching fact | New supported preference | Add |
| Older value for same fact | Newer supported value | Update |
| Existing fact explicitly withdrawn | Withdrawal evidence | Delete |
| Same normalized fact and revision | Duplicate observation | No-op |

| Boundary signal | Attention peak | Similarity valley | Split |
|---|---:|---:|---:|
| Topic transition | Yes | Yes | Yes |
| Lexical drift | false | true | false |
:::



`hybrid_topic_segments` splits a stream where an attention-boundary peak and a
semantic-similarity valley agree. The application extracts candidates from
those bounded groups. It classifies each candidate with a memory operation.
`plan_memory_mutations` validates the decisions and returns a storage-free
plan.

## How it works

Normalize boundary and adjacent-similarity arrays to the `n−1` gaps between `n` turns. A gap is eligible when its attention score is a local peak above the configured boundary threshold and its adjacent semantic similarity is below the valley threshold. Eligible gaps split consecutive, non-overlapping segments. Mutation planning then requires exactly one decision per candidate, validates update/delete targets against current IDs, rejects duplicate adds and conflicting operations on one target, and returns a deterministic plan.

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

**Classification remains application-owned.** Mari checks candidate coverage, target existence, add collisions, and conflicting target operations. `apply_memory_mutations` provides a side-effect-free preview. Storage remains the host's responsibility.

::: source-block
**Research basis**

[Mem0: memory extraction and update operations](https://arxiv.org/abs/2504.19413){.paper}[LightMem: topic-aware memory consolidation](https://arxiv.org/abs/2510.18866){.paper}

[The conjunctive peak/valley rule and mutation validation are Mari implementations. Model-based classification remains outside the library.]{.small}
:::
