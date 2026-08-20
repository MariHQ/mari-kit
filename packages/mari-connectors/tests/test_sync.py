from __future__ import annotations

import unittest

from mari_components import (
    DocumentACL, KnowledgeDocument, PollPage, Principal, SyncMode, Tombstone,
)
from mari_components.sync import ManifestEntry, SyncState, plan_sync


class SyncPlanningTests(unittest.TestCase):
    def document(self, ident: str, revision: str, body: str = "body") -> KnowledgeDocument:
        return KnowledgeDocument(ident, ident, body, revision=revision)

    def test_incremental_replay_is_idempotent(self):
        page = PollPage((self.document("a", "1"),), next_cursor="c1", snapshot_complete=True)
        first = plan_sync(SyncState(), page, mode=SyncMode.INCREMENTAL)
        second = plan_sync(first.state, page, mode=SyncMode.INCREMENTAL)
        self.assertEqual([item.external_id for item in first.upserts], ["a"])
        self.assertEqual(second.upserts, ())
        self.assertEqual(second.unchanged, ("a",))

    def test_acl_only_change_is_an_upsert_with_a_stable_provider_revision(self):
        public = self.document("a", "1")
        first = plan_sync(
            SyncState(), PollPage((public,), next_cursor="c1", snapshot_complete=True),
            mode=SyncMode.INCREMENTAL,
        )
        restricted = KnowledgeDocument(
            "a", "a", "body", revision="1",
            acl=DocumentACL("restricted", (Principal("group", "engineering"),)),
        )
        changed = plan_sync(
            first.state, PollPage((restricted,), next_cursor="c2", snapshot_complete=True),
            mode=SyncMode.INCREMENTAL,
        )
        self.assertEqual(changed.upserts, (restricted,))

    def test_incomplete_full_snapshot_holds_cursor_and_deletes_nothing(self):
        state = SyncState(
            cursor="old",
            manifest={"old": ManifestEntry("1"), "seen": ManifestEntry("1")},
        )
        first = plan_sync(
            state,
            PollPage((self.document("seen", "1"),), next_cursor="new", next_checkpoint="page:2"),
            mode=SyncMode.FULL,
        )
        self.assertEqual(first.deletes, ())
        self.assertEqual(first.state.cursor, "old")
        self.assertEqual(first.state.checkpoint, "page:2")
        final = plan_sync(
            first.state,
            PollPage(next_cursor="new", snapshot_complete=True),
            mode=SyncMode.FULL,
        )
        self.assertEqual([(item.external_id, item.reason) for item in final.deletes], [
            ("old", "absent_from_complete_snapshot")
        ])
        self.assertEqual(final.state.cursor, "new")

    def test_explicit_tombstone_applies_on_incomplete_incremental_page(self):
        state = SyncState(cursor="old", manifest={"gone": ManifestEntry("1")})
        plan = plan_sync(
            state,
            PollPage(tombstones=(Tombstone("gone"),), next_checkpoint="again"),
            mode=SyncMode.INCREMENTAL,
        )
        self.assertEqual(plan.deletes[0].external_id, "gone")
        self.assertNotIn("gone", plan.state.manifest)
        self.assertEqual(plan.state.cursor, "old")

    def test_empty_body_is_a_real_change(self):
        state = SyncState(manifest={"a": ManifestEntry("old")})
        plan = plan_sync(
            state,
            PollPage((self.document("a", "new", ""),), snapshot_complete=True),
            mode=SyncMode.INCREMENTAL,
        )
        self.assertEqual(plan.upserts[0].body, "")

    def test_conflicting_or_duplicate_page_fails(self):
        document = self.document("a", "1")
        with self.assertRaises(ValueError):
            plan_sync(SyncState(), PollPage((document, document)), mode=SyncMode.INCREMENTAL)
        with self.assertRaises(ValueError):
            plan_sync(
                SyncState(), PollPage((document,), (Tombstone("a"),)), mode=SyncMode.INCREMENTAL
            )


if __name__ == "__main__":
    unittest.main()
