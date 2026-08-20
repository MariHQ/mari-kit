# Knowledge lifecycle

This project runs evidence-validated fact, decision, glossary, FAQ, and digest
recipes, then evaluates an automatic-approval policy. Outputs are ordinary
immutable values; the host decides how to persist and review them.

```bash
MARI_EXAMPLE_MODEL=fixture python -m examples.knowledge_lifecycle.main
```

For a real OpenAI-compatible gateway, set `MARI_EXAMPLE_MODEL=openai` plus
`LLM_BASE_URL`, `LLM_TOKEN`, and `LLM_MODEL`.
