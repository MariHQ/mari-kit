# Email as conversation events

`mari_kit.documents.email` parses one RFC 822 message into an immutable
value with the sender's own words separated from quoted replies, forwarded
blocks and signatures. `mari_kit.documents.email_threads` rebuilds
threads when reply headers are missing and emits `KnowledgeEvent` values for
`segment_conversations`. Both modules are standard library only and never touch
the filesystem or the network: the host reads bytes and supplies locators.

## Parse one message

```python
from mari_kit.documents.email import parse_email

message = parse_email(raw_bytes, source="maildir/buy-r/inbox/1068")
message.own_text        # what this sender wrote, quotes and signature removed
message.fragments       # ordered own, quoted, forwarded, signature regions with offsets
message.subject_key     # subject with reply and forward prefixes stripped
message.bulk.is_bulk    # list headers, precedence, auto-submitted, no-reply sender
```

`raw_body` is kept beside `own_text` because quote strippers fail most often on
forwards. Every `Fragment` covers an exact `[start, end)` slice of `raw_body`,
so a downstream quote can always be located in the original. Pseudo-headers
inside a quoted or forwarded block (`From:`, `Sent:`, Lotus Notes `Name on
MM/DD/YYYY HH:MM AM`, and the two-line name then date form) populate the
fragment's `sender`, `timestamp`, `subject` and `recipients`.

Recognized separators: Outlook `-----Original Message-----`, Lotus Notes
`----- Forwarded by X on DATE -----` including the wrapped forms, `On DATE, X
wrote:` with common localized verbs, `Begin forwarded message:`, and `>`
prefixed runs. A message with no `Message-ID` receives a deterministic
`synthetic:` identifier derived from sender, timestamp, subject key and body.
Undeclared quoted-printable bodies are decoded when the `=20`, `=09` and soft
break density makes the encoding unambiguous.

## Rebuild threads without headers

```python
from mari_kit.documents.email_threads import email_events, thread_emails

threads = thread_emails(messages, gap_seconds=14 * 86400)
for thread in threads:
    events = email_events(thread, scope="company")
```

`thread_emails` deduplicates by `Message-ID`, then by sender, minute and body
digest, and links messages with a union-find over four edge sources applied in
order of confidence:

1. `In-Reply-To` and `References`, when present.
2. Quoted containment: a quoted or forwarded fragment in a later message matches
   an earlier message's own text. The shorter normalized text must be a prefix
   of the longer one and at least `minimum_match_characters` long, so differing
   endings never match.
3. Body subset: an earlier message's own text is contained in a later message's
   raw body.
4. Same subject key, at least one shared participant besides the sender, and
   inside `gap_seconds` of the latest earlier member. Subject alone never links.

Each link records a `LinkReason`. Candidate buckets are bounded to the nearest
64 messages in time, so large same-subject groups stay linear rather than
quadratic. Quoted or forwarded blocks whose original is not in the input become
`reconstructed` messages with a `reconstructed:` identifier, so a thread can
show the message that only survived inside someone's reply. `thread_id` is a
digest of the sorted member identifiers and is stable across reruns.

`email_events` emits one event per message with `thread_id` set, `role`
`"message"` for real messages and `"quoted"` for reconstructed ones, and the
subject and recipients as a short header above `own_text`. Messages with no own
text are skipped; their quoted content is already represented. Because
`segment_conversations` preserves explicit threads, one thread becomes one
episode unless it exceeds the character bound.

## Limits

Threading is heuristic where headers are absent. Same-subject daily reports to
the same recipients merge into one thread, and a reply that rewrites the
subject and quotes nothing stays separate. Signature detection is conservative
and may leave a signature in `own_text` rather than remove real text. Time zone
abbreviations in pseudo-headers are read as UTC; numeric offsets are honored.
Attachments are listed by filename only; nothing under an attachment or an
attached `message/rfc822` part is read as body text.

## Validation

Tests cover each separator style with synthetic messages, exact fragment
offsets, nested forwards, header-linked and header-free chains, subject
collisions with disjoint participants, fingerprint duplicates, reconstruction
deduplication, stable thread identifiers under reordering, and bounded matching
on several hundred same-prefix messages. No public corpus is used in tests.
Measured on a Lotus Notes era archive, content threading lowered single-message
episodes from 69 to 58 percent and removed 47 percent of characters as quoted
text; those figures are a baseline, not a claim about other corpora.
