from __future__ import annotations

import unittest

from mari_components import (
    DocumentACL,
    KnowledgeDocument,
    PollPage,
    Principal,
    SyncMode,
    Tombstone,
)
from mari_components.sync import ManifestEntry, SyncState, plan_sync, stream_sync


class SyncPlanningTests(unittest.TestCase):
    def document(
        self, ident: str, revision: str, body: str = "body"
    ) -> KnowledgeDocument:
        return KnowledgeDocument(
            source_id="fixture",
            external_id=ident,
            title=ident,
            body=body,
            revision=revision,
        )

    def entry(self, ident: str, fingerprint: str = "old") -> ManifestEntry:
        return ManifestEntry(
            fingerprint=fingerprint,
            revision="1",
            source_id="fixture",
            external_id=ident,
        )

    def test_incremental_replay_is_idempotent(self):
        page = PollPage(
            upserts=(self.document("a", "1"),), next_cursor="c1", snapshot_complete=True
        )
        first = plan_sync(
            SyncState(), page, source_id="fixture", mode=SyncMode.INCREMENTAL
        )
        second = plan_sync(
            first.state, page, source_id="fixture", mode=SyncMode.INCREMENTAL
        )
        self.assertEqual([item.document_id for item in first.upserts], ["fixture/a"])
        self.assertEqual(second.upserts, ())
        self.assertEqual(second.unchanged, ("fixture/a",))

    def test_state_rejects_documents_from_another_source(self):
        page = PollPage(
            upserts=(
                self.document("a", "1"),
                KnowledgeDocument(
                    source_id="other",
                    external_id="a",
                    title="a",
                    body="body",
                    revision="1",
                ),
            ),
            snapshot_complete=True,
        )
        with self.assertRaisesRegex(ValueError, "foreign sources"):
            plan_sync(SyncState(), page, source_id="fixture", mode=SyncMode.INCREMENTAL)

    def test_acl_and_tag_changes_are_upserts(self):
        public = self.document("a", "1")
        first = plan_sync(
            SyncState(),
            PollPage(upserts=(public,), snapshot_complete=True),
            source_id="fixture",
            mode=SyncMode.INCREMENTAL,
        )
        restricted = KnowledgeDocument(
            source_id="fixture",
            external_id="a",
            title="a",
            body="body",
            revision="1",
            acl=DocumentACL(
                visibility="restricted",
                principals=(Principal(kind="group", identifier="engineering"),),
            ),
        )
        changed = plan_sync(
            first.state,
            PollPage(upserts=(restricted,), snapshot_complete=True),
            source_id="fixture",
            mode=SyncMode.INCREMENTAL,
        )
        self.assertEqual(changed.upserts, (restricted,))

    def test_incomplete_full_snapshot_holds_cursor_and_reconciles_only_at_end(self):
        state = SyncState(
            cursor="old",
            manifest={
                "fixture/old": self.entry("old"),
                "fixture/seen": self.entry("seen"),
            },
        )
        first = plan_sync(
            state,
            PollPage(
                upserts=(self.document("seen", "1"),),
                next_cursor="new",
                next_checkpoint="page:2",
            ),
            source_id="fixture",
            mode=SyncMode.FULL,
        )
        self.assertEqual(first.deletes, ())
        self.assertEqual(
            (first.state.cursor, first.state.checkpoint), ("old", "page:2")
        )
        final = plan_sync(
            first.state,
            PollPage(next_cursor="new", snapshot_complete=True),
            source_id="fixture",
            mode=SyncMode.FULL,
        )
        self.assertEqual(
            [(item.document_id, item.reason) for item in final.deletes],
            [
                ("fixture/old", "absent_from_complete_snapshot"),
            ],
        )

    def test_explicit_tombstone_applies_to_incomplete_incremental_page(self):
        state = SyncState(cursor="old", manifest={"fixture/gone": self.entry("gone")})
        plan = plan_sync(
            state,
            PollPage(
                tombstones=(Tombstone(source_id="fixture", external_id="gone"),),
                next_checkpoint="again",
            ),
            source_id="fixture",
            mode=SyncMode.INCREMENTAL,
        )
        self.assertNotIn("fixture/gone", plan.state.manifest)
        self.assertEqual(plan.state.cursor, "old")

    def test_conflicting_or_duplicate_page_fails(self):
        document = self.document("a", "1")
        with self.assertRaises(ValueError):
            plan_sync(
                SyncState(),
                PollPage(upserts=(document, document)),
                source_id="fixture",
                mode=SyncMode.INCREMENTAL,
            )
        with self.assertRaises(ValueError):
            plan_sync(
                SyncState(),
                PollPage(
                    upserts=(document,),
                    tombstones=(Tombstone(source_id="fixture", external_id="a"),),
                ),
                source_id="fixture",
                mode=SyncMode.INCREMENTAL,
            )

    def test_stream_sync_is_lazy_and_carries_state(self):
        visited: list[str] = []

        def pages():
            visited.append("first")
            yield PollPage(upserts=(self.document("a", "1"),), next_checkpoint="p2")
            visited.append("second")
            yield PollPage(
                upserts=(self.document("b", "1"),),
                next_cursor="done",
                snapshot_complete=True,
            )

        plans = stream_sync(
            pages(), SyncState(), source_id="fixture", mode=SyncMode.INCREMENTAL
        )
        next(plans)
        self.assertEqual(visited, ["first"])
        second = next(plans)
        self.assertEqual(visited, ["first", "second"])
        self.assertIn("fixture/a", second.state.manifest)
        self.assertIn("fixture/b", second.state.manifest)

    def test_state_is_source_bound_versioned_and_mode_safe(self):
        first = plan_sync(
            SyncState(),
            PollPage(upserts=(self.document("a", "1"),), next_checkpoint="p2"),
            source_id="fixture",
            mode=SyncMode.FULL,
        )
        self.assertEqual((first.expected_generation, first.state.generation), (0, 1))
        self.assertEqual(first.state.source_id, "fixture")
        with self.assertRaisesRegex(ValueError, "belongs to"):
            plan_sync(
                first.state,
                PollPage(snapshot_complete=True),
                source_id="other",
                mode=SyncMode.FULL,
            )
        with self.assertRaisesRegex(ValueError, "cannot resume"):
            plan_sync(
                first.state,
                PollPage(snapshot_complete=True),
                source_id="fixture",
                mode=SyncMode.INCREMENTAL,
            )

    def test_provider_metadata_cannot_bypass_fingerprinting(self):
        first = plan_sync(
            SyncState(),
            PollPage(upserts=(self.document("a", "1"),), snapshot_complete=True),
            source_id="fixture",
            mode=SyncMode.INCREMENTAL,
        )
        changed = KnowledgeDocument(
            source_id="fixture",
            external_id="a",
            title="a",
            body="changed",
            revision="2",
            metadata={"unchanged": True},
        )
        second = plan_sync(
            first.state,
            PollPage(upserts=(changed,), snapshot_complete=True),
            source_id="fixture",
            mode=SyncMode.INCREMENTAL,
        )
        self.assertEqual(second.upserts, (changed,))


if __name__ == "__main__":
    unittest.main()
