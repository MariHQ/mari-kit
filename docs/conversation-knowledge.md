# Conversations and trajectories as searchable knowledge

`mari_components.conversation_knowledge` turns source events into revision-bound
episodes and model-proposed knowledge. Search can match vocabulary absent from
the original messages: for example, “Why does Mari delay summarizing Slack?”
can retrieve a discussion saying “wait until it settles” and “each reply costs
another call.” The source messages remain the evidence.

Run `python -m examples.conversation_knowledge_demo` from the repository root for a credential-free example.
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

## Compile and resolve a current snapshot

The application supplies normalized `events`, a model or fixture callback named
`generate`, and a cache mapping artifact cache keys to `EpisodeKnowledge` values.

```python
from mari_components.conversation_knowledge import (
    compile_episodes,
    evidence_context,
    segment_conversations,
)

episodes = segment_conversations(events)
result = compile_episodes(
    episodes,
    generate=generate,
    cache=cache,
    now=now_seconds,
    settle_seconds=300,
    maximum_calls=10,
    recipe="episode-extractor:model-v1:prompt-v3",
)

for artifact in result.artifacts:
    cache[artifact.cache_key] = artifact  # persist through the host's store
    context = evidence_context(
        artifact,
        current_events=events,
        allowed=can_read_event,
    )
```

`pending` contains episode IDs deferred by settling or the call budget. Schedule
another attempt in the host. A generator or parser exception propagates to the
caller, so the invocation returns no partial result. Use small batches or one
episode per invocation when independent failure recovery matters.

`evidence_context` verifies every event in the original episode, including events
outside the returned claim quotes. An edit, deletion, metadata change, or access
loss anywhere in that episode invalidates its context. Resolve against the
complete current event snapshot for that episode.

## Compose with shared update planning

Episode facets reuse Mari's `RetrievalUnit` contract. Their compiler currently
uses its own episode-revision and recipe cache, not the general dependency
planner automatically. Treat episode compilation as an application-owned
derivation when integrating it into a larger dependency graph.

Declare event membership, exact source revisions, and the extraction recipe as
inputs. Track embedding model configuration separately for facet vectors. Keep
retrieval projection and evidence freshness dependencies explicit so a reusable
vector never makes an obsolete source binding current. Scope filtering and
authorization checks still apply at query time.

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

## Research basis

- [LightMem](https://arxiv.org/abs/2510.18866) separates topic grouping, short-term
  extraction and offline updating. Its buffer-triggered extraction informed settled-episode
  compilation and explicit budgets. Mari supplies immutable plans/artifacts;
  it does not import LightMem's storage or model stack.
- [ReasoningBank paper](https://arxiv.org/abs/2509.25140) and
  [Google Research blog](https://research.google/blog/reasoningbank-enabling-agents-to-learn-from-experience/)
  motivate extracting reusable experience from successful and failed runs.
  Outcome-conditioned memory induction informs the design. Mari reuses its own
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
