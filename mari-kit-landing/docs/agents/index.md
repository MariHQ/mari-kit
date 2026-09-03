# Agents & procedures

## Choose an agent knowledge operation


| Input | Derived object | Activation boundary |
|---|---|---|
| Runtime events | Redacted normalized trajectory | Immediate record |
| Trace exports | OpenAI, Anthropic, or OTLP normalized steps | Unknown outcomes remain unknown |
| Trajectory corpus | Direct-follow graph, variants, rework, invariants | Caller reviews findings |
| Model-proposed intent | Evidence-bound intent candidate | Independent semantic review |
| Successful trajectories | Procedure candidate | Held-out gates and review |
| Reflections | Skillbook mutation proposal | Never auto-promoted |
| Reviewed procedure | Cached workflow match | Fresh and authorized dependencies required |

:::{collapse} Worked trajectory-to-procedure flow

| Observation | Derived result |
|---|---|
| Two successful runs share `lookup_policy → issue_refund` | Procedure candidate contains both stable steps |
| Failed run exits after `issue_refund` | Failure retained as negative evidence |
| Candidate improves score but leaks unauthorized context | Hard gate rejects promotion |
| Candidate passes all gates | Submitted for review; not activated automatically |
:::


```{toctree}
:maxdepth: 1

trajectories
trajectory-mining
intent-mining
procedural-learning
procedures
```
