# Google Drive change stream

This project demonstrates the complete Google Docs ingestion lifecycle:

1. enumerate an authoritative initial snapshot;
2. persist the returned native Changes cursor;
3. embed only planned document upserts and publish an initial index;
4. register a Google Drive push channel;
5. authenticate a notification's channel token and parse its dirty hint;
6. drain the Changes API rather than trusting the notification payload;
7. replace the edited document and its vectors, remove a deleted document and
   its vectors, embed a new document, persist an ACL-only update without
   recomputing unchanged vectors, and publish the next index generation.

Google push notifications contain no document body. They are wake-up hints;
the native Changes API is the reliable change stream.

Deterministic execution:

```bash
set -a
. examples/google_drive_change_stream/.env.example
set +a
python -m examples.google_drive_change_stream.main
```

For live mode, set `MARI_EXAMPLE_MODE=live`, use a current OAuth access token,
provide an HTTPS callback controlled by the host, and pass the exact received
notification headers in `GDRIVE_NOTIFICATION_HEADERS_JSON`. No value is
invented or selected implicitly.
