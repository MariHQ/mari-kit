# Email conversation events

## Parse source messages

```{code-block} python
from mari_kit.documents.email import parse_email

message = parse_email(raw_bytes, source="maildir/inbox/1068")
own_text = message.own_text
```

```{include} ../../../docs/email.md
:start-line: 2
```
