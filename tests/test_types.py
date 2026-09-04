from __future__ import annotations

import unittest

from mari_components import (
    DocumentACL,
    KnowledgeDocument,
    PollRequest,
    Principal,
    RevisionRef,
    parse_document_id,
)
from mari_components.http import HttpRequest


class TypesTests(unittest.TestCase):
    def test_document_requires_stable_identity(self):
        with self.assertRaises(ValueError):
            KnowledgeDocument(
                source_id="", external_id="x", title="Title", body="Body", revision="v1"
            )

    def test_document_timestamp_is_normalized_to_utc(self):
        document = KnowledgeDocument(
            source_id="notion",
            external_id="page:1",
            title="One",
            body="Body",
            revision="v1",
            updated_at="2026-08-19T18:42:07-07:00",
        )
        self.assertEqual(document.updated_at, "2026-08-20T01:42:07Z")

    def test_document_identity_frames_slashes_and_exposes_structural_ref(self):
        left = KnowledgeDocument(
            source_id="a/b", external_id="c", title="", body="", revision="1"
        )
        right = KnowledgeDocument(
            source_id="a", external_id="b/c", title="", body="", revision="1"
        )
        self.assertNotEqual(left.document_id, right.document_id)
        self.assertEqual(parse_document_id(left.document_id), ("a/b", "c"))
        self.assertIsInstance(left.ref, RevisionRef)
        self.assertEqual(left.ref.object.namespace, "a/b")

    def test_document_metadata_is_deeply_frozen(self):
        metadata = {"nested": ["first"]}
        document = KnowledgeDocument(
            source_id="source",
            external_id="item",
            title="",
            body="",
            revision="1",
            metadata=metadata,
        )
        metadata["nested"].append("outside")
        self.assertEqual(document.metadata["nested"], ("first",))

    def test_acl_is_explicit_and_immutable(self):
        acl = DocumentACL(
            visibility="restricted",
            principals=(Principal(kind="group", identifier="engineering"),),
        )
        document = KnowledgeDocument(
            source_id="notion",
            external_id="page:1",
            title="One",
            body="Body",
            revision="v1",
            acl=acl,
        )
        self.assertEqual(document.acl.principals[0].identifier, "engineering")
        with self.assertRaises(AttributeError):
            document.title = "Changed"  # type: ignore[misc]

    def test_poll_limits_are_positive(self):
        with self.assertRaises(ValueError):
            PollRequest(page_size=0)

    def test_http_request_repr_redacts_headers_body_and_query_credentials(self):
        request = HttpRequest(
            "POST",
            "https://user:password@api.example.test/items?key=secret&view=small&token=hidden",
            {
                "Authorization": "Bearer secret",
                "X-API-Key": "another",
                "Accept": "json",
            },
            b'{"password":"secret"}',
        )
        rendered = repr(request)
        self.assertNotIn("secret", rendered)
        self.assertNotIn("hidden", rendered)
        self.assertNotIn("another", rendered)
        self.assertNotIn("password", rendered)
        self.assertIn("view=small", rendered)
        self.assertIn("[REDACTED]", rendered)


if __name__ == "__main__":
    unittest.main()
