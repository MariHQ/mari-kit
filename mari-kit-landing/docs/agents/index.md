# Agents & procedures

## Evaluation

| Feature | Evaluation | Result | Corpus result |
|---|---|---:|---|
| [Trajectories](trajectories.md#evaluation) | 9 deterministic cases | 9 / 9 pass | AgentBench not measured |
| [Procedure learning](procedural-learning.md#evaluation) | 10 deterministic cases | 10 / 10 pass | Task uplift not measured |
| [Procedure representation](procedures.md#evaluation) | 10 deterministic cases | 10 / 10 pass | Voyager/Reflexion success not measured |
| Memory retrieval input | LongMemEval-S | Recall-all@10 `0.9021` | Reader accuracy not measured |

| Input | Derived object | Activation boundary |
|---|---|---|
| Runtime events | Redacted normalized trajectory | Immediate record |
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
procedural-learning
procedures
```
