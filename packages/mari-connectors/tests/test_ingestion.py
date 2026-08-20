from __future__ import annotations

import unittest

from mari_components import KnowledgeDocument, PollPage, SyncMode, Tombstone
from mari_components.sync import ManifestEntry, SyncState
from mari_components.sync.ingestion import AppliedPage, consume_connector_pages


class ConnectorIngestionApplicationTests(unittest.TestCase):
    def test_pages_are_applied_lazily_and_checkpointed_in_order(self) -> None:
        produced: list[str] = []
        applied: list[tuple[int, str | None]] = []

        def pages():
            produced.append("one")
            yield PollPage((KnowledgeDocument("one", "One", "body"),),
                           next_checkpoint="page-2", snapshot_complete=False)
            produced.append("two")
            yield PollPage((KnowledgeDocument("two", "Two", "body"),),
                           next_cursor="cursor-2", snapshot_complete=True)

        def apply(plan, number):
            applied.append((number, plan.state.checkpoint or plan.state.cursor))
            self.assertEqual(len(produced), number)
            return AppliedPage(inserted_ids=(number,), chunks=1, embeddings=1)

        report = consume_connector_pages(pages(), SyncState(), SyncMode.FULL, apply_page=apply)
        self.assertEqual(applied, [(1, "page-2"), (2, "cursor-2")])
        self.assertEqual(report.inserted_ids, (1, 2))
        self.assertTrue(report.snapshot_complete)

    def test_failure_does_not_pull_or_apply_a_later_page(self) -> None:
        produced: list[int] = []

        def pages():
            produced.append(1)
            yield PollPage(next_checkpoint="next")
            produced.append(2)
            yield PollPage(snapshot_complete=True)

        with self.assertRaisesRegex(RuntimeError, "commit failed"):
            consume_connector_pages(
                pages(), SyncState(), SyncMode.INCREMENTAL,
                apply_page=lambda _plan, _number: (_ for _ in ()).throw(RuntimeError("commit failed")),
            )
        self.assertEqual(produced, [1])

    def test_complete_full_snapshot_deletes_only_after_terminal_page(self) -> None:
        state = SyncState(manifest={
            "keep": ManifestEntry("old"), "gone": ManifestEntry("old"),
        })
        deleted: list[tuple[int, tuple[str, ...]]] = []

        def apply(plan, number):
            ids = tuple(item.external_id for item in plan.deletes)
            deleted.append((number, ids))
            return AppliedPage(deleted=len(ids))

        report = consume_connector_pages([
            PollPage((KnowledgeDocument("keep", "Keep", "body"),), next_checkpoint="p2"),
            PollPage(snapshot_complete=True, next_cursor="done"),
        ], state, SyncMode.FULL, apply_page=apply)
        self.assertEqual(deleted, [(1, ()), (2, ("gone",))])
        self.assertEqual(report.deleted, 1)

    def test_incremental_tombstone_is_applied_immediately(self) -> None:
        state = SyncState(manifest={"gone": ManifestEntry("old")})
        seen = []
        report = consume_connector_pages([
            PollPage(tombstones=(Tombstone("gone"),), next_cursor="done", snapshot_complete=True),
        ], state, SyncMode.INCREMENTAL, apply_page=lambda plan, _number: (
            seen.extend(item.external_id for item in plan.deletes) or AppliedPage(deleted=len(plan.deletes))
        ))
        self.assertEqual(seen, ["gone"])
        self.assertEqual(report.state.manifest, {})

    def test_empty_stream_and_page_after_terminal_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "no polling pages"):
            consume_connector_pages((), SyncState(), SyncMode.INCREMENTAL,
                                    apply_page=lambda *_args: AppliedPage())
        with self.assertRaisesRegex(ValueError, "after its terminal"):
            consume_connector_pages(
                [PollPage(snapshot_complete=True), PollPage(snapshot_complete=True)],
                SyncState(), SyncMode.INCREMENTAL, apply_page=lambda *_args: AppliedPage(),
            )


if __name__ == "__main__":
    unittest.main()
