from __future__ import annotations

import unittest

from mari_components.knowledge import (
    MemoryDecision,
    MemoryOperation,
    apply_memory_mutations,
    hybrid_topic_segments,
    plan_memory_mutations,
)


class MemoryMutationTests(unittest.TestCase):
    def test_four_operation_plan_is_auditable_and_storage_neutral(self):
        existing = {"old-role": "I work at A", "obsolete": "I use X"}
        candidates = {
            "c-add": "I live in Paris",
            "c-delete": "I stopped using X",
            "c-noop": "I work at A",
            "c-update": "I work at B",
        }
        plan = plan_memory_mutations(
            existing,
            candidates,
            {
                "c-add": MemoryDecision(operation=MemoryOperation.ADD),
                "c-delete": MemoryDecision(
                    operation=MemoryOperation.DELETE, target_id="obsolete"
                ),
                "c-noop": MemoryDecision(operation=MemoryOperation.NOOP),
                "c-update": MemoryDecision(
                    operation=MemoryOperation.UPDATE, target_id="old-role"
                ),
            },
        )
        self.assertEqual(len(plan.writes), 2)
        self.assertEqual(len(plan.deletes), 1)
        self.assertEqual(len(plan.noops), 1)
        self.assertEqual(
            apply_memory_mutations(existing, plan),
            {"old-role": "I work at B", "c-add": "I live in Paris"},
        )
        self.assertEqual(existing["old-role"], "I work at A")

    def test_missing_decision_and_conflicting_targets_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "decisions must match"):
            plan_memory_mutations({}, {"a": "A"}, {})
        with self.assertRaisesRegex(ValueError, "multiple mutations"):
            plan_memory_mutations(
                {"old": "old"},
                {"a": "A", "b": "B"},
                {
                    "a": MemoryDecision(
                        operation=MemoryOperation.UPDATE, target_id="old"
                    ),
                    "b": MemoryDecision(
                        operation=MemoryOperation.DELETE, target_id="old"
                    ),
                },
            )


class TopicSegmentationTests(unittest.TestCase):
    def test_boundary_requires_attention_peak_and_similarity_valley(self):
        segments = hybrid_topic_segments(
            ("a", "b", "c", "d", "e"),
            attention_boundaries=(0.1, 0.9, 0.2, 0.8),
            adjacent_similarities=(0.8, 0.2, 0.1, 0.1),
            similarity_threshold=0.4,
        )
        self.assertEqual(
            [segment.items for segment in segments], [("a", "b"), ("c", "d", "e")]
        )
        self.assertEqual(
            [(segment.start, segment.stop) for segment in segments], [(0, 2), (2, 5)]
        )

    def test_similarity_valley_without_attention_peak_does_not_split(self):
        segments = hybrid_topic_segments(
            ("a", "b", "c", "d"),
            attention_boundaries=(0.3, 0.2, 0.1),
            adjacent_similarities=(0.9, 0.0, 0.9),
            similarity_threshold=0.4,
        )
        self.assertEqual(
            [segment.items for segment in segments], [("a", "b", "c", "d")]
        )


if __name__ == "__main__":
    unittest.main()
