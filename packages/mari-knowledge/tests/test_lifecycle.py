import unittest

from mari_components.knowledge.lifecycle import DocumentPorts, ProjectionFields, delete, upsert
from mari_components.documents import DocumentVersion


def version(**changes):
    values = {
        "project_id": 7,
        "source_id": "12",
        "external_id": "page-1",
        "revision": "3",
        "title": "Runbook",
        "body": "Canonical text",
    }
    values.update(changes)
    return DocumentVersion(**values)


class DocumentApplicationTests(unittest.TestCase):
    def ports(self, calls, *, append=None, projected=None):
        def append_canonical(item):
            calls.append(("canonical", item.status))
            if append:
                append(item)

        return DocumentPorts(
            append_canonical=append_canonical,
            append_canonical_many=lambda items: [append_canonical(item) for item in items],
            delete_canonical=lambda item: calls.append(("tombstone", item.status)),
            delete_canonical_many=lambda items: calls.extend(
                ("tombstone", item.status) for item in items
            ),
            upsert_projection=lambda item, fields: calls.append(("projection", fields.kind)) or (42, True),
            projected_versions=lambda project_id, ids: projected or [],
            delete_projections=lambda project_id, ids: calls.append(("delete", tuple(ids))),
        )

    def test_upsert_writes_canonical_version_before_projection(self):
        calls = []
        result = upsert(
            version(), ProjectionFields(source="Confluence", kind="document", author="", author_initials=""),
            ports=self.ports(calls),
        )
        self.assertEqual((42, True), result)
        self.assertEqual([("canonical", "active"), ("projection", "document")], calls)

    def test_canonical_failure_never_writes_projection(self):
        calls = []

        def fail(_item):
            raise RuntimeError("warehouse unavailable")

        with self.assertRaisesRegex(RuntimeError, "warehouse unavailable"):
            upsert(
                version(), ProjectionFields(source="GitHub", kind="file", author="", author_initials=""),
                ports=self.ports(calls, append=fail),
            )
        self.assertEqual([("canonical", "active")], calls)

    def test_delete_records_every_tombstone_before_projection_removal(self):
        calls = []
        delete(7, [42, 43], reason="source removed", actor="connector", ports=self.ports(
            calls,
            projected=[version(external_id="a"), version(external_id="b")],
        ))
        self.assertEqual(
            [("tombstone", "deleted"), ("tombstone", "deleted"), ("delete", (42, 43))],
            calls,
        )

    def test_empty_delete_is_a_noop(self):
        calls = []
        delete(7, [], reason="unused", actor="connector", ports=self.ports(calls))
        self.assertEqual([], calls)


if __name__ == "__main__":
    unittest.main()
