[]{#context-lifecycle}[Current]{.current-label}

# Context lifecycle and selective intervention

## At a glance

| Comparison | Result | Design consequence |
|---|---:|---|
| Proactive memory agent vs. base agent, Terminal-Bench 2.0 | +8.3 percentage points | Recall must be able to intervene before a model call |
| Proactive memory agent vs. base agent, tau2-Bench | +6.8 percentage points | Intervention policy is separate from retrieval |
| PlugMem | Evaluates utility relative to context consumed | Record tokens and selected knowledge, not only task accuracy |

These are reported upstream results, not Mari measurements. Use them to justify measuring selective injection; they do not prescribe a model or agent loop.

## How it works

Mari separates four records that applications often collapse:

1. `SessionEvent` is the durable sequence of messages, tools, results, and errors.
2. `ContextRequest` describes the next model call, its purpose, scope, and budget.
3. `ContextEnvelope` contains only the knowledge selected for that call, with inclusion and exclusion traces.
4. `MemoryUpdatePlan` proposes what the completed model or tool event may change.

The provider may return `ABSTAIN`. Silence is a successful decision when retrieved knowledge is weak, redundant, unauthorized, stale, or more expensive than its predicted utility.

:::::::::{container} diagram flow
:::{container} card
**Observe**
Tool result or session event
:::
**→**
:::{container} card
**Retrieve**
Authorized candidates
:::
**→**
:::{container} card
**Decide**
Inject or abstain
:::
**→**
:::{container} card
**Measure**
Outcome and context cost
:::
:::::::::

```{code-block} python
:caption: Put Mari around a framework-owned model call

from mari_components.lifecycle import ContextRequest, LifecycleEvent, LifecyclePhase

request = ContextRequest(
    request_id="answer-refund-17",
    query="Can this order still be refunded?",
    purpose="customer_support",
    scopes=("user:42", "project:support"),
    token_budget=1_200,
)

envelope = await provider.before_model(request)
response = await model(user=request.query, context=envelope.text)
plan = await provider.after_model(
    LifecycleEvent(
        phase=LifecyclePhase.AFTER_MODEL,
        request_id=request.request_id,
        content=response,
    )
)
```

## API boundary

`ContextProvider` is an async protocol with `before_model`, `after_model`, `after_tool`, and `end_session`. Mari owns the values passed through that boundary. The host owns model execution, retry policy, persistence, and whether an accepted update plan is committed.

## What to evaluate

| Measure | Question |
|---|---|
| Intervention precision | When Mari injected memory, how often did it help? |
| Missed-intervention rate | How often was useful memory available but withheld? |
| Utility per 1,000 tokens | Did the result improve enough to justify the context? |
| Unsupported-memory rate | Did injected material lack valid evidence? |
| Task success delta | Did the same task improve with the provider enabled? |

::: source-block
**Papers and implementations**

[Remember When It Matters](https://arxiv.org/abs/2607.08716){.paper}[Official proactive-memory implementation](https://github.com/yifannnwu/proactive-memory-agent){.paper}[PlugMem](https://www.microsoft.com/en-us/research/publication/plugmem-a-task-agnostic-plugin-memory-module-for-llm-agents/){.paper}[OpenAI Agents lifecycle hooks](https://openai.github.io/openai-agents-python/ref/lifecycle/){.paper}

[Mari generalizes the lifecycle seam. It does not include an agent runtime or require an LLM-based intervention policy.]{.small}
:::
