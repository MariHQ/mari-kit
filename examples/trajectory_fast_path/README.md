# Observed trajectory fast path

This project consumes the lazy `run_tool_loop` event stream while the same live
events pass through the `observe` hook. Answers arrive as `answer_delta` events;
the loop does not assemble or buffer them. The project mines the observed
trajectories, deterministically distills repeated successful tool sequences,
matches a later request without an LLM call, and executes a host-approved fast
path. Telemetry arguments are never replayed.

```bash
MARI_EXAMPLE_MODEL=fixture \
WORKFLOW_MATCH_MINIMUM_SCORE=0.05 \
python -m examples.trajectory_fast_path.main
```

For a real OpenAI-compatible gateway, set `MARI_EXAMPLE_MODEL=openai` plus
`LLM_BASE_URL`, `LLM_TOKEN`, and `LLM_MODEL`.
