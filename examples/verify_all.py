"""Execute all projects with explicit deterministic environment values."""

from __future__ import annotations

import json

from examples.github_pipeline.main import run as run_github
from examples.google_drive_change_stream.main import run as run_drive
from examples.knowledge_lifecycle.main import run as run_lifecycle
from examples.slack_event_pipeline.main import run as run_slack
from examples.trajectory_fast_path.main import run as run_trajectory


def run() -> dict[str, object]:
    github = run_github({
        "MARI_EXAMPLE_MODE": "fake", "MARI_EXAMPLE_MODEL": "fixture",
        "GITHUB_TOKEN": "example-token", "GITHUB_REPOSITORY": "acme/knowledge",
        "GITHUB_PATHS": "README*,docs/**", "GITHUB_WEBHOOK_SECRET": "example-webhook-secret",
    })
    slack = run_slack({
        "MARI_EXAMPLE_MODE": "fake", "SLACK_BOT_TOKEN": "xoxb-example",
        "SLACK_SIGNING_SECRET": "example-secret", "SLACK_REQUEST_TIMESTAMP": "1000",
        "SLACK_CHANNELS": "engineering", "SLACK_HISTORY_TOKEN": "",
        "SLACK_ALLOWED_CHANNEL": "C-ENG",
    })
    trajectory = run_trajectory({
        "MARI_EXAMPLE_MODEL": "fixture", "WORKFLOW_MATCH_MINIMUM_SCORE": "0.05",
    })
    lifecycle = run_lifecycle({"MARI_EXAMPLE_MODEL": "fixture"})
    drive = run_drive({
        "MARI_EXAMPLE_MODE": "fake",
        "GDRIVE_ACCESS_TOKEN": "drive-example",
        "GDRIVE_FOLDER_ID": "",
        "GDRIVE_CALLBACK_URL": "https://knowledge.example/webhooks/google-drive",
        "GDRIVE_CHANNEL_ID": "example-channel",
        "GDRIVE_CHANNEL_TOKEN": "example-channel-token",
        "GDRIVE_NOTIFICATION_HEADERS_JSON": json.dumps({
            "X-Goog-Channel-ID": "example-channel",
            "X-Goog-Channel-Token": "example-channel-token",
            "X-Goog-Resource-ID": "example-resource",
            "X-Goog-Resource-State": "change",
            "X-Goog-Message-Number": "1",
        }),
    })
    checks = {
        "github_changes_planned": github["initial_upserts"] == (
            "file:README.md", "file:docs/release.md",
        ),
        "github_webhook_triggered_poll": github["event_poll_upserts"] == ("file:README.md",),
        "github_deletion_reconciled": github["event_poll_deletes"] == ("file:docs/release.md",),
        "github_poll_repairs_lost_event": github["scheduled_poll_repairs"] == (
            "file:README.md", "file:docs/operations.md",
        ),
        "vectors_searched": github["top_hit"] == "file:docs/release.md",
        "answer_grounded": github["citations"] == ("file:docs/release.md",),
        "slack_signature_verified": slack["signature_verified"] is True,
        "slack_event_refetched_thread": slack["stream_messages"] == 3,
        "slack_poll_repairs_lost_event": slack["final_messages"] == 4,
        "slack_acl_checked": slack["authorized"] is True,
        "agent_observed": trajectory["observed_events"] == 10,
        "workflow_distilled": trajectory["distilled_workflows"] == 1,
        "fast_path_reduces_online_llm_calls": trajectory["faster"] is True,
        "knowledge_lifecycle_completed": all(lifecycle[key] == 1 for key in (
            "facts", "decisions", "glossary_terms", "faq_answers", "digest_topics",
        )),
        "drive_change_stream_advanced": drive["cursor"] == "changes:stream-2",
        "drive_edit_reembedded": drive["embedding_changed_for_edit"] is True,
        "drive_delete_removed_vector": drive["deleted_vector_removed"] is True,
        "drive_acl_change_skipped_embedding": (
            drive["acl_only_change_not_reembedded"] is True
            and drive["acl_only_change_persisted"] is True
        ),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "projects": {
            "github": github, "slack": slack, "trajectory": trajectory,
            "knowledge_lifecycle": lifecycle,
            "google_drive": drive,
        },
    }


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
