# Knowledge lifecycle

This project keeps its DeepSeek prompts in the example, then passes the model
outputs through Mari's fact, decision, glossary, FAQ, and digest parsers. The
parsers validate exact evidence and attach the source revision. The example
demonstrates that a grounded fact becomes stale after its source changes; the
host decides persistence and review policy.

```bash
MARI_EXAMPLE_MODEL=fixture python -m examples.knowledge_lifecycle.main
```

For live generation, install `.[examples]` and set
`MARI_EXAMPLE_MODEL=deepseek`, `DEEPSEEK_API_KEY`, and `DEEPSEEK_MODEL`.
