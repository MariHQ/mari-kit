# Conversations and trajectories as searchable knowledge

`mari_components.conversation_knowledge` turns source events into revision-bound
episodes and model-proposed knowledge. Search can match vocabulary absent from
the original messages: for example, “Why does Mari delay summarizing Slack?”
can retrieve a discussion saying “wait until it settles” and “each reply costs
another call.” The source messages remain the evidence.

Run `python examples/conversation_knowledge_demo.py` for a credential-free example.
Its callback is a fixture, not a quality benchmark or a working model service.

## Integration

1. Normalize messages into `KnowledgeEvent`: stable event ID, revision, author,
   timestamp, source link, stream (channel/run) and application scope. Resolve
   edits/deletions first. Give a Slack root and its replies the same thread ID.
2. `segment_conversations` retains threads and splits unthreaded conversations
   on inactivity. Supply topic labels from a semantic segmenter to separate
   interleaved discussions. It does not guess whether shared participants imply
   a shared topic. Large episodes split at an explicit character bound; oversized
   single events are rejected for upstream splitting, not silently truncated.
3. `compile_episodes` defers active discussions, caps calls and reuses artifacts
   by episode revision plus recipe. Pass a callback that sends
   `request['instructions']` as the extraction instruction and serializes
   `request['events']` as source data. Configure provider output limits/timeouts
   in that callback. Include model, prompt, and settings versions in `recipe`.
4. Persist returned artifacts and cache keys; retry failed model calls in the
   host. The host reconciles the complete current episode set and deletes obsolete
   index entries after removed messages, splits or merges. Never leave old facets
   searchable after a source revision is replaced.
5. Embed `artifact.retrieval_units()` independently: summary, likely questions,
   topic names. These are ordinary Mari `RetrievalUnit` values. Fuse/aggregate
   their matches by episode ID; three facets are not three independent sources.
6. Before returning content, call `evidence_context` with current source events
   and an authorization predicate. Missing, changed or forbidden evidence fails
   closed. Scope metadata is for filtering, not an authorization implementation.
7. `topic_history` returns chronological episodes sharing a caller/model topic
   label within one scope. It preserves disagreements and revisions of opinion;
   chronology alone does not establish supersession. Resolve each episode's
   freshness and authorization before displaying a history.

## Extraction contract

The injected model returns a JSON object with `title`, `topics`, `questions` and
`claims`. Each claim has `text`, `kind`, `status` and nonempty `evidence`:

```json
{
  "title": "Thread summarization timing",
  "topics": ["ingestion cost"],
  "questions": ["Why delay extraction?"],
  "claims": [{
    "text": "Eric proposed batching.",
    "kind": "decision",
    "status": "proposed",
    "evidence": [{"event_id": "m1", "revision": "r1",
                  "start": 0, "end": 12, "quote": "Batch later."}]
  }]
}
```

Allowed kinds: summary, decision, rationale, alternative, disagreement,
open_question, lesson, procedure, failure. Status is explicit, inferred,
proposed or unresolved. Every factual summary assertion belongs in a claim.
Titles/questions/topics are search hints, not independently established facts.
The parser checks exact quote spans and source revisions. It does **not** prove
entailment, detect every malicious instruction, or decide who has authority to
approve a decision. Use review or a separately measured verifier for promotion.

## Knowledge in LLM trajectories

`trajectory_events` accepts existing Mari `TrajectoryRun` values and explicitly
supplied observations keyed by step ordinal. Include relevant tool results,
user instructions, visible assistant messages or provided rationale in those
observations. Tool telemetry alone cannot recover the contents of documents an
agent read. Do not fabricate missing reasoning or infer overall success from a
successful tool response. The adapter records step and run outcomes, including
unknown/failure, alongside the supplied content. The same episode compiler can
extract discoveries, procedures, failure lessons, alternatives and unresolved
questions from these events. Applicability should be recorded in lesson text.

## Research and local implementation review

- [LightMem](https://arxiv.org/abs/2510.18866) separates topic grouping, short-term
  extraction and offline updating. Inspected local
  `~/memory/LightMem/src/lightmem/factory/memory_buffer/short_term_memory.py`
  and `memory/lightmem.py`: buffer-triggered extraction informed settled-episode
  compilation and explicit budgets. Mari supplies immutable plans/artifacts;
  it does not import LightMem's storage or model stack.
- [ReasoningBank paper](https://arxiv.org/abs/2509.25140) and
  [Google Research blog](https://research.google/blog/reasoningbank-enabling-agents-to-learn-from-experience/)
  motivate extracting reusable experience from successful and failed runs.
  Inspected `~/memory/experience-reasoning-bank/WebArena/induce_memory.py`,
  including outcome-conditioned memory induction. Mari reuses its own
  `TrajectoryRun` contract and requires observable content explicitly.

This is an original implementation informed by those projects; no upstream code
was copied, and their reported benchmark results do not transfer to this module.
The existing Mari trajectory episode/reflection and reasoning-memory parsers
remain available for deeper process analysis; this module adds the searchable
knowledge and source-resolution bridge for both chats and runs.

## Validation and limits

Tests cover thread/tenant boundaries, hard limits, exact evidence validation,
edits and access revocation, failure observations, novel search vocabulary,
settling and revision cache behavior. For semantic quality, freeze held-out
conversations and traces with independently labeled questions and evidence.
Compare raw-message retrieval against summary/question/episode retrieval, count
unsupported claims and mistaken decisions, and measure evidence recall and model
calls. No live extraction quality or retrieval benchmark is claimed here.

Cross-thread topic discovery, automatic topic alias resolution, semantic
entailment checks, persistent queues, embedding stores and production connector
integration are host responsibilities. The example shows the complete library
path without prescribing a provider or launching paid model calls.
