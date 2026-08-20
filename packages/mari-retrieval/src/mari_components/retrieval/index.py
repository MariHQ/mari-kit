"""Immutable in-memory MUVERA index built from arbitrary embedding vectors."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

import numpy as np
from numpy.typing import NDArray

from .maxsim import exact_maxsim
from .muvera import FDEConfig, encode_fde, projection_parameters
from .polarquant import PolarCodec, polar_scores, train_polar


def _readonly(value: NDArray) -> NDArray:
    copy = np.array(value, copy=True)
    copy.flags.writeable = False
    return copy


@dataclass(frozen=True, slots=True)
class MuveraIndex:
    document_ids: tuple[str, ...]
    offsets: NDArray[np.int64]
    vectors: NDArray[np.float32]
    packed: NDArray[np.uint8]
    codec: PolarCodec
    config: FDEConfig
    input_dimension: int
    hashes: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.document_ids:
            raise ValueError("index must contain at least one document")
        if len(set(self.document_ids)) != len(self.document_ids):
            raise ValueError("document IDs must be unique")
        if len(self.offsets) != len(self.document_ids) + 1:
            raise ValueError("invalid offset count")
        if int(self.offsets[0]) != 0 or int(self.offsets[-1]) != len(self.vectors):
            raise ValueError("invalid vector offsets")
        if np.any(np.diff(self.offsets) <= 0):
            raise ValueError("each document must have at least one vector")
        if self.vectors.ndim != 2 or self.vectors.shape[1] != self.input_dimension:
            raise ValueError("invalid vector matrix")
        if self.packed.shape != (len(self.document_ids), self.codec.packed_bytes):
            raise ValueError("invalid packed matrix")
        object.__setattr__(self, "offsets", _readonly(self.offsets).astype(np.int64, copy=False))
        object.__setattr__(self, "vectors", _readonly(self.vectors).astype(np.float32, copy=False))
        object.__setattr__(self, "packed", _readonly(self.packed).astype(np.uint8, copy=False))
        object.__setattr__(self, "hashes", MappingProxyType(dict(self.hashes)))


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    document_id: str
    score: float
    approximate_score: float


def build_index(
    documents: Mapping[str, NDArray[np.floating]],
    config: FDEConfig | None = None,
    *,
    hashes: Mapping[str, str] | None = None,
) -> MuveraIndex:
    cfg = config or FDEConfig()
    clean: dict[str, NDArray[np.float32]] = {}
    for raw_id, matrix in documents.items():
        document_id = str(raw_id)
        values = np.asarray(matrix, np.float32)
        if not document_id:
            raise ValueError("document ID is required")
        if values.ndim != 2 or not len(values) or values.shape[1] < 1:
            raise ValueError(f"document {document_id!r} has an invalid vector matrix")
        clean[document_id] = values
    if not clean:
        raise ValueError("cannot build an empty vector index")
    dimensions = {int(value.shape[1]) for value in clean.values()}
    if len(dimensions) != 1:
        raise ValueError("all document vectors must share one dimension")
    document_ids = tuple(sorted(clean))
    input_dimension = dimensions.pop()
    parameters = projection_parameters(cfg, input_dimension)
    fdes = np.stack(
        [encode_fde(clean[document_id], cfg, parameters, query=False) for document_id in document_ids]
    ).astype(np.float32)
    codec, packed = train_polar(fdes)
    offsets = np.zeros(len(document_ids) + 1, np.int64)
    offsets[1:] = np.cumsum([len(clean[document_id]) for document_id in document_ids])
    vectors = np.concatenate([clean[document_id] for document_id in document_ids]).astype(np.float32)
    known_hashes = {document_id: (hashes or {}).get(document_id, "") for document_id in document_ids}
    return MuveraIndex(
        document_ids,
        offsets,
        vectors,
        packed,
        codec,
        cfg,
        input_dimension,
        known_hashes,
    )


def search_index(
    index: MuveraIndex,
    query_vectors: NDArray[np.floating],
    *,
    limit: int = 10,
    candidate_limit: int = 1000,
) -> tuple[RetrievalHit, ...]:
    if limit < 1 or candidate_limit < 1:
        raise ValueError("limit and candidate_limit must be positive")
    query = np.asarray(query_vectors, np.float32)
    if query.ndim != 2 or not len(query) or query.shape[1] != index.input_dimension:
        raise ValueError("query vectors do not match the index dimension")
    parameters = projection_parameters(index.config, index.input_dimension)
    query_fde = encode_fde(query, index.config, parameters, query=True)
    approximate = polar_scores(index.packed, query_fde, index.codec)
    take = min(max(limit, candidate_limit), len(approximate))
    positions = (
        np.argpartition(-approximate, take - 1)[:take]
        if take < len(approximate)
        else np.arange(len(approximate))
    )
    exact = np.asarray(
        [
            exact_maxsim(
                query,
                index.vectors[int(index.offsets[position]) : int(index.offsets[position + 1])],
            )
            for position in positions
        ],
        np.float32,
    )
    order = np.argsort(-exact, kind="stable")[: min(limit, len(exact))]
    return tuple(
        RetrievalHit(
            index.document_ids[int(positions[position])],
            float(exact[position]),
            float(approximate[int(positions[position])]),
        )
        for position in order
    )
