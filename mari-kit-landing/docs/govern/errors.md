[]{#errors}[Core]{.current-label}

# Errors and deliberate boundaries

## Contract

| Failure class | Library behavior |
|---|---|
| Invalid caller input | Raise a specific validation error before mutation |
| Malformed model output | Return uncertainty or a typed parse issue where recovery is safe |
| Transport or rate-limit failure | Classify for caller-owned retry policy |
| Revision conflict | Reject the stale write. Preserve the current value |


:::{collapse} Example failure mapping

| Observed condition | Raised boundary | Host action |
|---|---|---|
| Incomplete full snapshot | `IncompleteSnapshot` | Preserve prior state. Deletion requires an authoritative snapshot |
| Expired credentials | `AuthenticationFailure` | Refresh credentials |
| Valid request receives throttling | `TransientFailure` | Apply host retry budget |
| Model omits required evidence | `MalformedModelOutput` | Retry or abstain |
:::



## How it works

Exceptions identify the failed boundary and its retry signal. Connector adapters
translate provider responses into authentication failures or transient errors.
Permanent failures use another category. Snapshot validation raises
`IncompleteSnapshot`. Absence has its own state, apart from deletion. Knowledge
parsers raise `MalformedModelOutput` before an invalid value enters typed state.
The host owns retry budgets and clocks. Credentials and side effects also stay
there, along with retry execution.

| Error | Meaning | Typical handling |
|----|----|----|
| `AuthenticationFailure` | Credentials rejected | Request new credentials |
| `TransientFailure` | Temporary provider failure | Retry using app policy |
| `PermanentFailure` | Request cannot succeed unchanged | Require intervention |
| `IncompleteSnapshot` | Listing lacks authority | Deletion requires an authoritative snapshot |
| `MalformedModelOutput` | Generated value violates parser contract | Retry or abstain |

## Safe representations and connector contracts

Credentials are excluded from connector configuration representations. `HttpRequest` representations redact authorization headers, bodies, URL userinfo, and common sensitive query parameters. `check_connector_contract` provides an executable contract check for third-party connector implementations.

```{code-block} python
:caption: connector_test.py

from mari_components import SyncMode
from mari_components.testing import check_connector_contract

pages = tuple(my_connector(config, request, http=fake_http))
report = check_connector_contract(pages, mode=SyncMode.FULL,
    starting_cursor=request.cursor)
assert report.pages == len(pages)
```

Application components: model client, prompt framework, database, scheduler,
credential store, authorization engine, agent runtime, and worker queue.

**Engineering contract.** This taxonomy defines control flow and safe defaults. Provider APIs have distinct failure semantics. Each adapter maps its protocol into these categories before application retry policy runs.
