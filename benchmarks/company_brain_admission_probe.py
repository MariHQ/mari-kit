"""Measure whether an oversized user view displaces a warm small-user view."""

import json
from dataclasses import asdict
from tempfile import TemporaryDirectory

from examples.company_brains.durable.engine import CompanyBrain
from examples.company_brains.durable.store import SQLiteBrainStore
from mari_kit import (
    DocumentACL,
    KnowledgeDocument,
    PollPage,
    Principal,
    ScopeRef,
    SyncMode,
)
from mari_kit.sync import plan_sync


class CountingStore(SQLiteBrainStore):
    snapshot_reads = 0

    def access_token_snapshot(self, scope, user_id):
        self.snapshot_reads += 1
        return super().access_token_snapshot(scope, user_id)


def run() -> dict:
    scope = ScopeRef(tenant="admission-probe")
    public = KnowledgeDocument(
        source_id="handbook",
        external_id="public",
        title="Refund policy",
        body="Refunds require approval.",
        revision="v1",
        acl=DocumentACL(visibility="public"),
    )
    large = KnowledgeDocument(
        source_id="handbook",
        external_id="large",
        title="Large refund source",
        body="Refund evidence. " * 10000,
        revision="v1",
        acl=DocumentACL(
            visibility="restricted",
            principals=(Principal(kind="user", identifier="large-user"),),
        ),
    )
    with TemporaryDirectory(prefix="brain-admission-") as directory:
        with CountingStore(directory) as store:
            plan = plan_sync(
                store.state(scope, "handbook"),
                PollPage(upserts=(public, large), snapshot_complete=True),
                source_id="handbook",
                mode=SyncMode.FULL,
            )
            store.apply_plan(scope, plan)
            brain = CompanyBrain(store, scope, view_cache_bytes=32768)
            brain.search("refund", user_id="small-user")
            warm = asdict(brain.cache_stats())
            brain.search("refund", user_id="large-user")
            after_large = asdict(brain.cache_stats())
            before = store.snapshot_reads
            small_results = brain.search("refund", user_id="small-user")
            return {
                "byte_budget": 32768,
                "warm_small_user": warm,
                "after_oversized_user": after_large,
                "small_user_snapshot_reloads": store.snapshot_reads - before,
                "small_user_visible_ids": [doc.document_id for doc in small_results],
                "final": asdict(brain.cache_stats()),
            }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
