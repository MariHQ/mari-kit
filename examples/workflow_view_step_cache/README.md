# WorkflowView step-level answer cache

This example applies the hierarchical abstraction from
[WorkflowView](https://arxiv.org/abs/2606.14654) to a completed support-agent
trajectory:

```text
atomic tool events
  -> Layer 1: detailed description and contiguous activity phases
  -> Layer 2: high-level workflow intent
  -> reviewed, evidence-grounded answers for reusable phases
```

The original request asks both whether a customer's plan includes SSO and how
to configure it. The extracted entitlement and configuration phases become two
independent cache entries. A later request can reuse either answer without
requiring the entire original request to match. Each entry records only the
document revision that grounds that answer, so changing the entitlement policy
invalidates the entitlement answer without invalidating the setup answer.

This extends WorkflowView's descriptive layers with an application-owned cache
admission step. The host accepts only reviewed cache keys, checks that phase
ranges cover the telemetry exactly, verifies every quote against its source,
and requires each dependency document to have been read inside that phase.

The example also demonstrates why the cache gate is stricter than workflow
matching: an exact subquestion is reusable, the compound request is not treated
as a canned-answer hit, and a paraphrase changes from miss to hit when the host
intentionally lowers its cache threshold.

Run the deterministic acceptance version:

```bash
set -a; . examples/workflow_view_step_cache/.env.example; set +a
python -m examples.workflow_view_step_cache.main
```

For real inference, select `live` mode in `.env.example`. DeepSeek performs the
two WorkflowView layers through its OpenAI-compatible API using the official
OpenAI Python SDK. OpenAI generates all embeddings in one batched request. The
example makes no provider calls in fixture mode.

This is an offline post-trajectory extraction example, matching the paper's
near-term deployment guidance. A production host should review extracted cache
candidates before admitting them and persist the resulting reviewed workflows.
