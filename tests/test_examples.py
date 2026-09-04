from __future__ import annotations

import json
import unittest

from examples.cross_user_acl_isolation.main import run as run_acl_isolation
from examples.github_pipeline.main import run as run_github
from examples.google_drive_change_stream.main import run as run_drive
from examples.incident_response_drift.main import run as run_incident_drift
from examples.knowledge_lifecycle.main import run as run_lifecycle
from examples.slack_event_pipeline.main import run as run_slack
from examples.slackbot_reliable_answers.main import run as run_slackbot
from examples.verify_all import run as verify_all
from examples.workflow_view_step_cache.main import run as run_workflow_view

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
SLACKBOT_ENV = {
    "MARI_EXAMPLE_MODE": "fake",
    "MARI_EXAMPLE_MODEL": "fixture",
    "MARI_EXAMPLE_EMBEDDINGS": "fixture",
    "MARI_SPECULATION_THRESHOLD": "0.70",
    "MARI_CACHE_THRESHOLD": "0.97",
}
DRIVE_ENV = {
    "MARI_EXAMPLE_MODE": "fake",
    "GDRIVE_ACCESS_TOKEN": "drive-example",
    "GDRIVE_FOLDER_ID": "",
    "GDRIVE_CALLBACK_URL": "https://knowledge.example/webhooks/google-drive",
    "GDRIVE_CHANNEL_ID": "example-channel",
    "GDRIVE_CHANNEL_TOKEN": "example-channel-token",
    "GDRIVE_NOTIFICATION_HEADERS_JSON": json.dumps(
        {
            "X-Goog-Channel-ID": "example-channel",
            "X-Goog-Channel-Token": "example-channel-token",
            "X-Goog-Resource-ID": "example-resource",
            "X-Goog-Resource-State": "change",
            "X-Goog-Message-Number": "1",
        }
    ),
}
WORKFLOW_VIEW_ENV = {
    "MARI_EXAMPLE_MODE": "fake",
    "MARI_EXAMPLE_MODEL": "fixture",
    "MARI_EXAMPLE_EMBEDDINGS": "fixture",
    "MARI_CACHE_THRESHOLD": "0.97",
}


class RunnableExampleTests(unittest.TestCase):
    def test_projects_require_explicit_environment(self):
        with self.assertRaisesRegex(RuntimeError, "MARI_EXAMPLE_MODE is required"):
            run_github({})
        with self.assertRaisesRegex(RuntimeError, "MARI_EXAMPLE_MODE is required"):
            run_slack({})
        with self.assertRaisesRegex(RuntimeError, "MARI_EXAMPLE_MODE is required"):
            run_slackbot({})
        with self.assertRaisesRegex(RuntimeError, "MARI_EXAMPLE_MODEL is required"):
            run_lifecycle({})
        with self.assertRaisesRegex(RuntimeError, "MARI_EXAMPLE_MODE is required"):
            run_drive({})
        with self.assertRaisesRegex(RuntimeError, "MARI_EXAMPLE_MODE is required"):
            run_workflow_view({})
        with self.assertRaisesRegex(RuntimeError, "MARI_EXAMPLE_MODE is required"):
            run_acl_isolation({})
        with self.assertRaisesRegex(RuntimeError, "MARI_EXAMPLE_MODE is required"):
            run_incident_drift({})

    def test_acl_isolation_applies_to_retrieval_and_cached_answers(self):
        result = run_acl_isolation({"MARI_EXAMPLE_MODE": "fake"})
        self.assertEqual(result["customer_allowed_document_ids"], ("status/checkout",))
        self.assertEqual(result["customer_retrieval_hits"], ("status/checkout",))
        self.assertEqual(result["employee_workflow"], "internal-checkout-mitigation")
        self.assertEqual(result["customer_workflow"], "public-checkout-status")
        self.assertTrue(result["restricted_document_hidden_from_customer"])
        self.assertTrue(result["both_users_received_grounded_cache"])

    def test_github_change_pipeline_uses_separate_functions(self):
        result = run_github(GITHUB_ENV)
        self.assertEqual(
            result["initial_upserts"],
            (
                "file:README.md",
                "file:docs/release.md",
            ),
        )
        self.assertTrue(result["initial_cursor_advanced"])
        self.assertEqual(result["top_hit"], "file:docs/release.md")
        self.assertEqual(
            result["citations"],
            ("github:acme%2Fknowledge@c2b742db362c223f/file:docs%2Frelease.md",),
        )
        self.assertTrue(result["webhook_verified"])
        self.assertEqual(result["coalesced_events"], 1)
        self.assertEqual(result["event_poll_upserts"], ("file:README.md",))
        self.assertEqual(result["event_poll_deletes"], ("file:docs/release.md",))
        self.assertEqual(
            result["scheduled_poll_repairs"],
            (
                "file:README.md",
                "file:docs/operations.md",
            ),
        )
        self.assertEqual(
            result["remaining"],
            (
                "file:README.md",
                "file:docs/operations.md",
            ),
        )

    def test_signed_slack_event_refetches_and_plans_canonical_thread(self):
        result = run_slack(SLACK_ENV)
        self.assertTrue(result["signature_verified"])
        self.assertEqual(result["coalesced_events"], 1)
        self.assertEqual(
            result["initial_polled_documents"], ("thread:C-ENG:100.000001",)
        )
        self.assertEqual(result["initial_messages"], 2)
        self.assertEqual(
            result["stream_updated_documents"], ("thread:C-ENG:100.000001",)
        )
        self.assertEqual(result["stream_messages"], 3)
        self.assertEqual(
            result["polling_repaired_documents"], ("thread:C-ENG:100.000001",)
        )
        self.assertEqual(result["final_messages"], 4)
        self.assertEqual(result["poll_cursor"], "103.000001")
        self.assertEqual(result["visibility"], "restricted")
        self.assertTrue(result["authorized"])

    def test_slackbot_uses_reviewed_trajectory_cache_and_revision_dependencies(self):
        result = run_slackbot(SLACKBOT_ENV)
        self.assertEqual(result["deepseek_answer_rounds"], 1)
        self.assertEqual(result["deepseek_analysis_rounds"], 1)
        self.assertTrue(result["styleguide_applied"])
        self.assertGreaterEqual(result["verified_evidence_blocks"], 1)
        self.assertTrue(result["speculative_tool_called"])
        self.assertEqual(
            result["retrieved_document_ids"], ("mari/styleguide", "mari/refund-policy")
        )
        self.assertTrue(result["trajectory_analyzed_after_answer"])
        self.assertTrue(result["cache_hit"])
        self.assertEqual(result["impacted_artifacts"], ("workflow:support-refunds",))
        self.assertEqual(
            result["action_after_document_change"], "speculative_retrieval"
        )
        self.assertEqual(
            result["new_document_unreviewed_action"], "speculative_retrieval"
        )
        self.assertEqual(result["new_document_nonimpacting_action"], "cached_response")
        self.assertEqual(
            result["new_document_impacting_action"], "speculative_retrieval"
        )

    def test_knowledge_lifecycle_returns_reviewable_values(self):
        result = run_lifecycle({"MARI_EXAMPLE_MODEL": "fixture"})
        self.assertEqual(result["facts"], 1)
        self.assertEqual(result["decisions"], 1)
        self.assertEqual(result["glossary_terms"], 1)
        self.assertEqual(result["faq_answers"], 1)
        self.assertEqual(result["digest_topics"], 1)
        self.assertEqual(result["initial_freshness"], "current")
        self.assertEqual(result["freshness_after_source_edit"], "stale")
        self.assertFalse(result["stale_fact_reusable"])

    def test_workflow_view_caches_and_invalidates_individual_steps(self):
        result = run_workflow_view(WORKFLOW_VIEW_ENV)
        self.assertEqual(result["deepseek_layer_rounds"], 2)
        self.assertEqual(result["openai_embedding_calls"], 1)
        self.assertEqual(result["cacheable_steps"], ("sso-entitlement", "sso-setup"))
        self.assertTrue(result["entitlement_cache_hit"])
        self.assertTrue(result["setup_cache_hit"])
        self.assertNotEqual(result["compound_request_action"], "cached_response")
        self.assertNotEqual(result["strict_threshold_action"], "cached_response")
        self.assertEqual(result["relaxed_threshold_action"], "cached_response")
        self.assertEqual(
            result["impacted_after_entitlement_change"],
            ("workflow:sso-entitlement",),
        )
        self.assertEqual(result["entitlement_after_change"], "speculative_retrieval")
        self.assertEqual(result["setup_after_change"], "cached_response")

    def test_incident_drift_invalidates_only_changed_runbook_section(self):
        result = run_incident_drift({"MARI_EXAMPLE_MODE": "fake"})
        self.assertEqual(
            result["impacted_artifacts"],
            (
                "answer:checkout-mitigation",
                "digest:whole-checkout-runbook",
                "workflow:checkout-mitigation",
            ),
        )
        self.assertEqual(
            result["mitigation_action_after_change"], "speculative_retrieval"
        )
        self.assertEqual(
            result["mitigation_sources"],
            (
                "github:acme%2Foperations/checkout-runbook.md",
                "slack:acme/thread:checkout-1042",
            ),
        )
        self.assertEqual(result["escalation_action_after_change"], "cached_response")
        self.assertTrue(result["unchanged_escalation_cache_preserved"])

    def test_google_drive_edit_replaces_vectors_and_delete_removes_them(self):
        result = run_drive(DRIVE_ENV)
        self.assertEqual(result["initial_documents"], ("doc-1", "doc-2", "doc-4"))
        self.assertEqual(result["changed_documents"], ("doc-1", "doc-3", "doc-4"))
        self.assertEqual(result["deleted_documents"], ("doc-2",))
        self.assertEqual(
            result["embedded_documents"],
            (
                "doc-1",
                "doc-2",
                "doc-4",
                "doc-1",
                "doc-3",
            ),
        )
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
