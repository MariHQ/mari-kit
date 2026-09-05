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

Semantic grouping and offline topic relationships are available through the
companion module below. Automatic topic naming/alias governance, semantic
entailment checks, persistent queues, embedding stores and production connector
integration remain host responsibilities.

## Group interleaved conversations and reconnect episodes

`mari_components.conversation_topics` adds an embedding-based path. Run
`python -m examples.conversation_topics_demo` for the complete credential-free
example, including extraction, topic grouping, relationship proposals, original
evidence, and an unchanged second pass with no consolidation calls.

```python
from mari_components.conversation_topics import (
    event_vector_key,
    knowledge_vector_key,
    semantic_conversation_episodes,
    semantic_topic_groups,
)

# embed is your application's batch embedding function; use one embedding space.
loose = [event for event in events if not event.thread_id]
event_vectors = dict(zip(
    [event_vector_key(event) for event in loose],
    embed([event.text for event in loose]),
    strict=True,
))
episodes = semantic_conversation_episodes(events, vectors=event_vectors)
# Compile these episodes using compile_episodes, then:
artifacts = extracted.artifacts
topic_vectors = dict(zip(
    [knowledge_vector_key(a) for a in artifacts],
    embed([a.retrieval_units()[0].text for a in artifacts]),
    strict=True,
))
groups = semantic_topic_groups(artifacts, vectors=topic_vectors)
```

Unthreaded events group within scope, stream, supplied topic label, and a bounded
time window. Explicit threads retain their original events and size bounds.
The algorithm uses deterministic greedy complete-link grouping: every member
must meet the similarity threshold with every other member. This prevents a
chain of weakly related messages from merging unrelated topics. It is a bounded
quadratic algorithm, not a scalable all-corpus clustering service. Partition
inputs before the default 1,000-candidate limit. Default thresholds are starting
points, not calibrated values for every embedding model.

Episode grouping can reconnect conversations across streams and days without
matching topic labels. Always pass an authorized partition; company scope alone
does not imply identical channel permissions. Version embedding model/configuration
in the host cache namespace. Keys bind exact inputs but cannot detect vectors
produced by different same-dimensional models. This is an embedding-only
adaptation, not LightMem's LLMLingua compression/attention model implementation.

## Consolidate topic briefs incrementally

`compile_topic_briefs` accepts groups, a JSON-producing `generate` callback,
`cache`, `current_events`, `allowed`, and `count_tokens`. It returns `briefs`,
`pending`, `retired`, dependency `receipts`, callback `calls`, `reserved_tokens`,
and `reused`. Current source evidence for the entire batch is checked before
any model call, including when cache entries are available.

The model sees the cited claims plus source events and proposes `supports`,
`contradicts`, `extends`, or `supersedes` links between claim IDs from different
episodes. Empty links are valid. Endpoint IDs are validated against the exact
input group. Titles are search hints; rationales and links are explicitly
unverified proposals. Briefs retain every original claim, including conflicting
positions. A supersession proposal never deletes evidence or establishes an
approved decision. The result is an extractive brief with proposed relationships,
not a verified, authoritative narrative synthesis.

`brief.retrieval_units()` emits brief and question facets. Their revisions
fingerprint the actual output, so changed text cannot reuse a previous vector
revision. `topic_evidence_context` resolves all original events again before
display, rejecting source edits, deletions, or access loss. Filter/authorize
derived facets before search too; a query-time renderer does not secure an
unfiltered shared index.

The call cap counts callback invocations. The token budget reserves the supplied
whole-request token count plus `output_token_reserve` per call. Use an accurate
provider tokenizer and enforce that output cap in the callback; retries and
provider-hidden overhead cannot be bounded by the library. Malformed outputs
raise without returning partial results. Use small batches for failure recovery.

Cache keys include full extracted member content and the recipe. Change the
recipe with the model, prompt, parser, or generation configuration. Persist
briefs and receipts atomically in the host. `topic_dependencies` exposes a
`DerivationSpec` and exact member/membership stamps for `plan_dependency_updates`.
The compiler uses its exact-input cache and emits compatible receipts; it does
not run a background dependency executor.

Supply the complete active partition and its previous topic IDs to calculate
retirements. Membership changes can create a new topic ID: remove retired index
entries after splits, merges, and deletions. Withheld/pending new revisions must
not leave old evidence searchable. Stable, human-curated topic IDs are not yet
provided. Durable queues, token-triggered extraction buffers, and multi-episode
model-request batching remain unimplemented; no service is started by this API.

Fixture tests cover interleaving, cross-day links, transitive-drift prevention,
scope boundaries, invalid vectors/links, edit invalidation, retirement, budgets,
dependency receipt reuse, and incremental-versus-clean equality. The example
uses planted embeddings and model outputs. Evaluate real held-out channel and
trajectory questions before claiming semantic retrieval improvements. Lossy
compression remains deliberately disabled until such evaluation exists.
