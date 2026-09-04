# Agents & procedures

## Operations


| Input | Derived object | Activation boundary |
|---|---|---|
| [Conversations and trajectory observations](conversation-knowledge.md) | Searchable episodes with exact source evidence | Current sources and authorization checked on read |
| Runtime events | Redacted normalized trajectory | Immediate record |
| Trace exports | OpenAI, Anthropic, or OTLP normalized steps | Unknown outcomes remain unknown |
| Trajectory corpus | Direct-follow graph, variants, rework, invariants | Caller reviews findings |
| Model-proposed intent | Evidence-bound intent candidate | Independent semantic review |
| Successful trajectories | Procedure candidate | Held-out gates and review |
| Reflections | Skillbook mutation proposal | Manual promotion |
| Reviewed procedure | Cached workflow match | Fresh and authorized dependencies required |

:::{collapse} Trajectory-to-procedure example

| Observation | Derived result |
|---|---|
| Two successful runs share `lookup_policy → issue_refund` | Procedure candidate contains both stable steps |
| Failed run exits after `issue_refund` | Failure retained as negative evidence |
| Candidate improves score and leaks unauthorized context | Hard gate rejects promotion |
| Candidate passes all gates | Submitted for review. Activation requires an application commit |
:::


```{toctree}
:maxdepth: 1

conversation-knowledge
trajectories
trajectory-mining
intent-mining
procedural-learning
procedures
```
