"""Execute all projects with explicit deterministic environment values."""

from __future__ import annotations

import json

from examples.cross_user_acl_isolation.main import run as run_acl_isolation
from examples.github_pipeline.main import run as run_github
from examples.google_drive_change_stream.main import run as run_drive
from examples.incident_response_drift.main import run as run_incident_drift
from examples.knowledge_lifecycle.main import run as run_lifecycle
from examples.quickstarts.agent_knowledge import run as run_agent_knowledge
from examples.quickstarts.company_search import run as run_company_search
from examples.quickstarts.dependency_updates import run as run_dependency_updates
from examples.quickstarts.governed_knowledge import run as run_governed_knowledge
from examples.quickstarts.knowledge_maintenance import run as run_knowledge_maintenance
from examples.slack_event_pipeline.main import run as run_slack
from examples.slackbot_reliable_answers.main import run as run_slackbot
from examples.workflow_view_step_cache.main import run as run_workflow_view


def run() -> dict[str, object]:
    company_search = run_company_search()
    governed_knowledge = run_governed_knowledge()
    agent_knowledge = run_agent_knowledge()
    dependency_updates = run_dependency_updates()
    knowledge_maintenance = run_knowledge_maintenance()
    acl_isolation = run_acl_isolation({"MARI_EXAMPLE_MODE": "fake"})
    github = run_github(
        {
            "MARI_EXAMPLE_MODE": "fake",
            "MARI_EXAMPLE_MODEL": "fixture",
            "GITHUB_TOKEN": "example-token",
            "GITHUB_REPOSITORY": "acme/knowledge",
            "GITHUB_PATHS": "README*,docs/**",
            "GITHUB_WEBHOOK_SECRET": "example-webhook-secret",
        }
    )
    slack = run_slack(
        {
            "MARI_EXAMPLE_MODE": "fake",
            "SLACK_BOT_TOKEN": "xoxb-example",
            "SLACK_SIGNING_SECRET": "example-secret",
            "SLACK_REQUEST_TIMESTAMP": "1000",
            "SLACK_CHANNELS": "engineering",
            "SLACK_HISTORY_TOKEN": "",
            "SLACK_ALLOWED_CHANNEL": "C-ENG",
        }
    )
    slackbot = run_slackbot(
        {
            "MARI_EXAMPLE_MODE": "fake",
            "MARI_EXAMPLE_MODEL": "fixture",
            "MARI_EXAMPLE_EMBEDDINGS": "fixture",
            "MARI_SPECULATION_THRESHOLD": "0.70",
            "MARI_CACHE_THRESHOLD": "0.97",
        }
    )
    lifecycle = run_lifecycle({"MARI_EXAMPLE_MODEL": "fixture"})
    incident_drift = run_incident_drift({"MARI_EXAMPLE_MODE": "fake"})
    workflow_view = run_workflow_view(
        {
            "MARI_EXAMPLE_MODE": "fake",
            "MARI_EXAMPLE_MODEL": "fixture",
            "MARI_EXAMPLE_EMBEDDINGS": "fixture",
            "MARI_CACHE_THRESHOLD": "0.97",
        }
    )
    drive = run_drive(
        {
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
    )
    checks = {
        "conversation_maintenance_matches_clean_rebuild": (
            knowledge_maintenance["incremental_equals_rebuild"] is True
            and knowledge_maintenance["vectors_rebuilt"] == 1
        ),
        "dependency_updates_equal_rebuild_and_preserve_evidence": (
            dependency_updates["incremental_equals_rebuild"] is True
            and dependency_updates["vectors_rebuilt"] == 1
            and dependency_updates["retrieved_current_evidence"] is True
            and dependency_updates["lineage_reaches_atom_inputs"] is True
        ),
        "company_search_is_authorized_and_revision_bound": (
            company_search["revision"] == "policy-v1"
            and "30 days" in str(company_search["text"])
        ),
        "structured_evidence_commits_a_governed_artifact": (
            governed_knowledge["artifact"] is not None
            and len(governed_knowledge["evidence"]) == 1
        ),
        "completed_activity_produces_a_reviewable_proposal": (
            agent_knowledge["target_id"] == "procedure:refund-answer"
        ),
        "acl_retrieval_isolated_before_scoring": (
            acl_isolation["restricted_document_hidden_from_customer"] is True
            and acl_isolation["customer_retrieval_hits"] == ("status/checkout",)
        ),
        "acl_cache_isolated_before_matching": (
            acl_isolation["employee_workflow"] == "internal-checkout-mitigation"
            and acl_isolation["customer_workflow"] == "public-checkout-status"
            and acl_isolation["both_users_received_grounded_cache"] is True
        ),
        "github_changes_planned": github["initial_upserts"]
        == (
            "file:README.md",
            "file:docs/release.md",
        ),
        "github_webhook_triggered_poll": github["event_poll_upserts"]
        == ("file:README.md",),
        "github_deletion_reconciled": github["event_poll_deletes"]
        == ("file:docs/release.md",),
        "github_poll_repairs_lost_event": github["scheduled_poll_repairs"]
        == (
            "file:README.md",
            "file:docs/operations.md",
        ),
        "vectors_searched": github["top_hit"] == "file:docs/release.md",
        "answer_grounded": github["citations"]
        == ("github:acme%2Fknowledge@c2b742db362c223f/file:docs%2Frelease.md",),
        "slack_signature_verified": slack["signature_verified"] is True,
        "slack_event_refetched_thread": slack["stream_messages"] == 3,
        "slack_poll_repairs_lost_event": slack["final_messages"] == 4,
        "slack_acl_checked": slack["authorized"] is True,
        "slackbot_one_answer_round": slackbot["deepseek_answer_rounds"] == 1,
        "slackbot_posthoc_analysis_round": slackbot["deepseek_analysis_rounds"] == 1,
        "slackbot_managed_voice": slackbot["styleguide_applied"] is True,
        "slackbot_evidence_verified": slackbot["verified_evidence_blocks"] >= 1,
        "slackbot_speculative_retrieval": slackbot["speculative_tool_called"] is True,
        "slackbot_trajectory_analyzed": slackbot["trajectory_analyzed_after_answer"]
        is True,
        "slackbot_high_threshold_cache": slackbot["cache_hit"] is True,
        "slackbot_dependency_invalidated": (
            slackbot["impacted_artifacts"] == ("workflow:support-refunds",)
            and slackbot["action_after_document_change"] == "speculative_retrieval"
        ),
        "slackbot_new_doc_falls_back": (
            slackbot["new_document_unreviewed_action"] == "speculative_retrieval"
            and slackbot["new_document_nonimpacting_action"] == "cached_response"
            and slackbot["new_document_impacting_action"] == "speculative_retrieval"
        ),
        "workflow_view_extracts_intra_workflow_answers": (
            workflow_view["cacheable_steps"] == ("sso-entitlement", "sso-setup")
            and workflow_view["entitlement_cache_hit"] is True
            and workflow_view["setup_cache_hit"] is True
        ),
        "workflow_view_does_not_cache_compound_request": (
            workflow_view["compound_request_action"] != "cached_response"
        ),
        "workflow_view_cache_threshold_is_tunable": (
            workflow_view["strict_threshold_action"] != "cached_response"
            and workflow_view["relaxed_threshold_action"] == "cached_response"
        ),
        "workflow_view_invalidates_only_affected_step": (
            workflow_view["impacted_after_entitlement_change"]
            == ("workflow:sso-entitlement",)
            and workflow_view["entitlement_after_change"] == "speculative_retrieval"
            and workflow_view["setup_after_change"] == "cached_response"
        ),
        "knowledge_lifecycle_completed": all(
            lifecycle[key] == 1
            for key in (
                "facts",
                "decisions",
                "glossary_terms",
                "faq_answers",
                "digest_topics",
            )
        ),
        "reviewed_fact_invalidated": (
            lifecycle["initial_freshness"] == "current"
            and lifecycle["freshness_after_source_edit"] == "stale"
            and lifecycle["stale_fact_reusable"] is False
        ),
        "incident_drift_reports_all_impacted_artifacts": (
            incident_drift["impacted_artifacts"]
            == (
                "answer:checkout-mitigation",
                "digest:whole-checkout-runbook",
                "workflow:checkout-mitigation",
            )
            and incident_drift["mitigation_sources"]
            == (
                "github:acme%2Foperations/checkout-runbook.md",
                "slack:acme/thread:checkout-1042",
            )
        ),
        "incident_drift_preserves_unchanged_section_cache": (
            incident_drift["mitigation_action_after_change"] == "speculative_retrieval"
            and incident_drift["escalation_action_after_change"] == "cached_response"
        ),
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
            "cross_user_acl_isolation": acl_isolation,
            "github": github,
            "slack": slack,
            "slackbot_reliable_answers": slackbot,
            "knowledge_lifecycle": lifecycle,
            "incident_response_drift": incident_drift,
            "google_drive": drive,
            "workflow_view_step_cache": workflow_view,
        },
    }


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
