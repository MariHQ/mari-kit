from __future__ import annotations

import json
import unittest

from examples.github_pipeline.main import run as run_github
from examples.google_drive_change_stream.main import run as run_drive
from examples.knowledge_lifecycle.main import run as run_lifecycle
from examples.slack_event_pipeline.main import run as run_slack
from examples.trajectory_fast_path.main import run as run_trajectory
from examples.verify_all import run as verify_all


GITHUB_ENV = {
    "MARI_EXAMPLE_MODE": "fake",
    "MARI_EXAMPLE_MODEL": "fixture",
    "GITHUB_TOKEN": "example-token",
    "GITHUB_REPOSITORY": "acme/knowledge",
    "GITHUB_PATHS": "README*,docs/**",
    "GITHUB_WEBHOOK_SECRET": "example-webhook-secret",
}
SLACK_ENV = {
    "MARI_EXAMPLE_MODE": "fake",
    "SLACK_BOT_TOKEN": "xoxb-example",
    "SLACK_SIGNING_SECRET": "example-secret",
    "SLACK_REQUEST_TIMESTAMP": "1000",
    "SLACK_CHANNELS": "engineering",
    "SLACK_HISTORY_TOKEN": "",
    "SLACK_ALLOWED_CHANNEL": "C-ENG",
}
TRAJECTORY_ENV = {
    "MARI_EXAMPLE_MODEL": "fixture",
    "WORKFLOW_MATCH_MINIMUM_SCORE": "0.05",
}
DRIVE_ENV = {
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
}


class RunnableExampleTests(unittest.TestCase):
    def test_projects_require_explicit_environment(self):
        with self.assertRaisesRegex(RuntimeError, "MARI_EXAMPLE_MODE is required"):
            run_github({})
        with self.assertRaisesRegex(RuntimeError, "MARI_EXAMPLE_MODE is required"):
            run_slack({})
        with self.assertRaisesRegex(RuntimeError, "MARI_EXAMPLE_MODEL is required"):
            run_trajectory({})
        with self.assertRaisesRegex(RuntimeError, "MARI_EXAMPLE_MODEL is required"):
            run_lifecycle({})
        with self.assertRaisesRegex(RuntimeError, "MARI_EXAMPLE_MODE is required"):
            run_drive({})

    def test_github_change_pipeline_uses_separate_functions(self):
        result = run_github(GITHUB_ENV)
        self.assertEqual(result["initial_upserts"], (
            "file:README.md", "file:docs/release.md",
        ))
        self.assertTrue(result["initial_cursor_advanced"])
        self.assertEqual(result["top_hit"], "file:docs/release.md")
        self.assertEqual(result["citations"], ("file:docs/release.md",))
        self.assertTrue(result["webhook_verified"])
        self.assertEqual(result["coalesced_events"], 1)
        self.assertEqual(result["event_poll_upserts"], ("file:README.md",))
        self.assertEqual(result["event_poll_deletes"], ("file:docs/release.md",))
        self.assertEqual(result["scheduled_poll_repairs"], (
            "file:README.md", "file:docs/operations.md",
        ))
        self.assertEqual(result["remaining"], (
            "file:README.md", "file:docs/operations.md",
        ))

    def test_signed_slack_event_refetches_and_plans_canonical_thread(self):
        result = run_slack(SLACK_ENV)
        self.assertTrue(result["signature_verified"])
        self.assertEqual(result["coalesced_events"], 1)
        self.assertEqual(result["initial_polled_documents"], ("thread:C-ENG:100.000001",))
        self.assertEqual(result["initial_messages"], 2)
        self.assertEqual(result["stream_updated_documents"], ("thread:C-ENG:100.000001",))
        self.assertEqual(result["stream_messages"], 3)
        self.assertEqual(result["polling_repaired_documents"], ("thread:C-ENG:100.000001",))
        self.assertEqual(result["final_messages"], 4)
        self.assertEqual(result["poll_cursor"], "103.000001")
        self.assertEqual(result["visibility"], "restricted")
        self.assertTrue(result["authorized"])

    def test_observed_trajectories_distill_to_a_faster_path(self):
        result = run_trajectory(TRAJECTORY_ENV)
        self.assertEqual(result["observed_runs"], 2)
        self.assertEqual(result["observed_events"], 10)
        self.assertEqual(result["distilled_workflows"], 1)
        self.assertEqual(result["workflow_tools"], ("search",))
        self.assertEqual(result["workflow_occurrences"], 2)
        self.assertEqual(result["online_planner_calls_per_request"], 2)
        self.assertEqual(result["fast_path_model_calls"], 1)
        self.assertTrue(result["faster"])

    def test_knowledge_lifecycle_returns_reviewable_values(self):
        result = run_lifecycle({"MARI_EXAMPLE_MODEL": "fixture"})
        self.assertEqual(result["facts"], 1)
        self.assertEqual(result["decisions"], 1)
        self.assertEqual(result["glossary_terms"], 1)
        self.assertEqual(result["faq_answers"], 1)
        self.assertEqual(result["digest_topics"], 1)
        self.assertEqual(result["approval"], "manual")

    def test_google_drive_edit_replaces_vectors_and_delete_removes_them(self):
        result = run_drive(DRIVE_ENV)
        self.assertEqual(result["initial_documents"], ("doc-1", "doc-2", "doc-4"))
        self.assertEqual(result["changed_documents"], ("doc-1", "doc-3", "doc-4"))
        self.assertEqual(result["deleted_documents"], ("doc-2",))
        self.assertEqual(result["embedded_documents"], (
            "doc-1", "doc-2", "doc-4", "doc-1", "doc-3",
        ))
        self.assertTrue(result["embedding_changed_for_edit"])
        self.assertTrue(result["deleted_vector_removed"])
        self.assertTrue(result["acl_only_change_not_reembedded"])
        self.assertTrue(result["acl_only_change_persisted"])
        self.assertEqual(result["current_index_documents"], ("doc-1", "doc-3", "doc-4"))
        self.assertEqual(result["top_hit_after_edit"], "doc-1")
        self.assertEqual(result["cursor"], "changes:stream-2")

    def test_google_drive_rejects_a_notification_for_another_channel_token(self):
        environment = dict(DRIVE_ENV)
        headers = json.loads(environment["GDRIVE_NOTIFICATION_HEADERS_JSON"])
        headers["X-Goog-Channel-Token"] = "wrong-token"
        environment["GDRIVE_NOTIFICATION_HEADERS_JSON"] = json.dumps(headers)
        with self.assertRaisesRegex(RuntimeError, "channel token does not match"):
            run_drive(environment)

    def test_combined_proof_report_passes_every_workflow(self):
        report = verify_all()
        self.assertTrue(report["passed"])
        self.assertTrue(all(report["checks"].values()))


if __name__ == "__main__":
    unittest.main()
