[]{#errors}[Current]{.current-label}

# Errors and deliberate boundaries

## At a glance

| Failure class | Library behavior |
|---|---|
| Invalid caller input | Raise a specific validation error before mutation |
| Malformed model output | Return uncertainty or a typed parse issue where recovery is safe |
| Transport or rate-limit failure | Classify for caller-owned retry policy |
| Revision conflict | Reject the stale write; never overwrite silently |


:::{collapse} Worked failure mapping

| Observed condition | Raised boundary | Host action |
|---|---|---|
| Incomplete full snapshot | `IncompleteSnapshot` | Preserve prior state; do not infer deletes |
| Expired credentials | `AuthenticationFailure` | Refresh credentials |
| Valid request receives throttling | `TransientFailure` | Apply host retry budget |
| Model omits required evidence | `MalformedModelOutput` | Retry or abstain |
:::



## How it works

Exceptions classify which boundary failed and whether repeating the same request can help. Connector adapters translate provider responses into authentication, transient, or permanent failures. Snapshot validation raises `IncompleteSnapshot` before absence can become deletion. Knowledge parsers raise `MalformedModelOutput` before an invalid value crosses into typed state. Mari never retries automatically because retry budgets, clocks, credentials, and side effects belong to the host.

| Error | Meaning | Typical handling |
|----|----|----|
| `AuthenticationFailure` | Credentials rejected | Request new credentials |
| `TransientFailure` | Temporary provider failure | Retry using app policy |
| `PermanentFailure` | Request cannot succeed unchanged | Require intervention |
| `IncompleteSnapshot` | Listing is not authoritative | Do not infer deletion |
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

Not included: model client, prompt framework, database, scheduler, credential store, authorization engine, agent runtime, or worker queue.

**Engineering contract.** This taxonomy defines control flow and safe defaults. It is not a claim that provider APIs share identical failure semantics; each adapter maps its protocol into these categories before application retry policy is applied.
