from __future__ import annotations

import unittest

import numpy as np

from mari_components.retrieval import (
    FDEConfig,
    build_index,
    deserialize_index,
    encode_fde,
    exact_maxsim,
    polar_scores,
    projection_parameters,
    search_index,
    serialize_index,
    train_polar,
)


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.config = FDEConfig(repetitions=2, simhash_bits=2, projection_dimension=4)
        self.documents = {
            "10": np.asarray([[1, 0, 0], [0.9, 0.1, 0]], np.float32),
            "20": np.asarray([[0, 1, 0], [0.1, 0.9, 0]], np.float32),
            "30": np.asarray([[0, 0, 1]], np.float32),
        }

    def test_matches_existing_muvera_asymmetry(self):
        points = np.asarray([[1, 0, 0], [1, 0, 0]], np.float32)
        parameters = projection_parameters(self.config, 3)
        query = encode_fde(points, self.config, parameters, query=True)
        document = encode_fde(points, self.config, parameters, query=False)
        self.assertEqual(query.shape, (self.config.dimension,))
        self.assertFalse(np.allclose(query, document))

    def test_fde_is_invariant_to_provider_vector_magnitude(self):
        parameters = projection_parameters(self.config, 3)
        unit = np.asarray([[1, 2, 3]], np.float32)
        np.testing.assert_allclose(
            encode_fde(unit, self.config, parameters, query=False),
            encode_fde(unit * 17, self.config, parameters, query=False),
        )

    def test_polarquant_is_half_bit_and_finite(self):
        values = np.random.default_rng(4).normal(size=(9, self.config.dimension)).astype(np.float32)
        codec, packed = train_polar(values)
        self.assertEqual(packed.shape, (9, self.config.dimension // 16))
        self.assertEqual(codec.bits_per_fde_coordinate, 0.5)
        self.assertTrue(np.isfinite(polar_scores(packed, values[0], codec)).all())

    def test_exact_rerank(self):
        index = build_index(self.documents, self.config)
        hits = search_index(index, np.asarray([[0.95, 0.05, 0]], np.float32), limit=2)
        self.assertEqual(hits[0].document_id, "10")
        self.assertGreater(hits[0].score, hits[1].score)

    def test_serialization_round_trip_is_search_equivalent(self):
        index = build_index(self.documents, self.config, hashes={"10": "a"})
        files = serialize_index(index)
        restored = deserialize_index(files)
        query = np.asarray([[0.05, 0.95, 0]], np.float32)
        self.assertEqual(search_index(index, query), search_index(restored, query))
        self.assertEqual(restored.hashes["10"], "a")
        with self.assertRaises(ValueError):
            restored.vectors[0, 0] = 42

    def test_corruption_is_rejected(self):
        files = dict(serialize_index(build_index(self.documents, self.config)))
        files["vectors.npy"] += b"corrupt"
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            deserialize_index(files)

    def test_maxsim_rewards_each_query_vector_without_mutation(self):
        query = np.asarray([[1, 0], [0, 1]], np.float32)
        original = query.copy()
        both = np.asarray([[1, 0], [0, 1]], np.float32)
        one = np.asarray([[1, 0]], np.float32)
        self.assertGreater(exact_maxsim(query, both), exact_maxsim(query, one))
        np.testing.assert_array_equal(query, original)

    def test_invalid_shapes_fail_explicitly(self):
        with self.assertRaises(ValueError):
            build_index({})
        with self.assertRaises(ValueError):
            build_index({"x": np.asarray([], np.float32)})
        index = build_index(self.documents, self.config)
        with self.assertRaises(ValueError):
            search_index(index, np.ones((1, 4), np.float32))


if __name__ == "__main__":
    unittest.main()
