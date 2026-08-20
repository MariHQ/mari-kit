# Mari Components

Mari Components is a collection of infrastructure-neutral functions for
building product-knowledge systems. It provides connector polling and event
normalization, replay-safe sync planning, MUVERA/PolarQuant retrieval, grounded
knowledge recipes, trajectory mining, tool loops, and agent evaluations.

It is not a framework and has no application or `KnowledgeBase` object. A host
configures each connector, consumes its `PollPage` change stream, applies
`plan_sync`, persists the returned state and changes, invokes its own embedder,
and builds or publishes retrieval indexes itself.

```python
config = GitHubConfig(token, repository, paths=("README*", "docs/**"))
validation = validate_github(config, http=http)

state = load_sync_state(source_id)
for page in poll_github(config, poll_request(state), http=http):
    plan = plan_sync(state, page, mode=SyncMode.INCREMENTAL)
    persist_documents(plan.upserts, plan.deletes)
    embed(plan.upserts)
    save_sync_state(plan.state)
    state = plan.state
```

The package deliberately does not own a database, web framework, authentication,
queue, object store, model provider, embedding model, or process lifecycle.
Callers inject HTTP and model functions and pass vectors into retrieval.

Agent execution is also transport-neutral and streaming. `run_tool_loop`
returns a lazy iterator: tool calls, tool results, and answer deltas reach the
caller as they happen. The host decides whether those events become SSE,
WebSocket messages, CLI output, or observability records.

```python
for event in run_tool_loop(
    messages,
    tools,
    generate_json=choose_action,
    stream_answer=generate_answer_chunks,
    authorize_write=authorize_write,
    observe=record_trajectory_event,
):
    publish(event)
```

The loop never builds a final answer or retains emitted events. Consumers that
need a complete answer or an offline evaluation can explicitly collect the
`answer_delta` events at that boundary.

Knowledge extraction never accepts model-reported confidence. Facts,
decisions, checks, FAQs, and grounded answers receive a deterministic evidence
confidence computed from exact-quote coverage, independent source count, and
citation count. The public `evidence_confidence` function lets hosts apply the
same calculation to their own recipes.

See [SCOPE.md](SCOPE.md) for the architecture boundary.

## Executable projects

Each directory under `examples/` is an executable project with a documented
environment contract. No example chooses credentials, providers, repositories,
models, or live/fake mode implicitly.

- [GitHub polling and webhook stream](examples/github_pipeline/README.md): poll
  authoritative repository state, verify/coalesce webhook hints, trigger
  canonical incremental sync, update derived vectors, and repair a deliberately
  missed webhook with the next scheduled poll.
- [Slack polling and event stream](examples/slack_event_pipeline/README.md): poll
  initial channel history, immediately refetch a thread from a signed reply
  event, then repair a deliberately missed event through periodic polling while
  preserving the same canonical document and ACL.
- [Trajectory fast path](examples/trajectory_fast_path/README.md): collect
  agent events through an observability hook, mine trajectories, distill a
  repeated workflow, match it without another LLM call, and execute a
  host-approved fast path with fewer online model invocations.
- [Knowledge lifecycle](examples/knowledge_lifecycle/README.md): produce
  evidence-validated facts, decisions, glossary terms, FAQs, and digests, then
  evaluate approval policy without writing application state.
- [Google Drive change stream](examples/google_drive_change_stream/README.md):
  snapshot Google Docs, register a push channel, drain native changes, re-embed
  edits, remove deleted vectors, and publish the next retrieval generation.

Execute the deterministic projects and emit a machine-readable proof report:

```bash
python -m examples.verify_all
```

Execute the complete verification suite:

```bash
python -m unittest discover -s tests -p 'test_*.py'
```
