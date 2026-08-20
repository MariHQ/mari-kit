"""Deterministic 0.5-bit block-2 PolarQuant encoding for MUVERA FDEs."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class PolarCodec:
    dimension: int
    angle_centers: tuple[float, float]
    radius: float
    boundary: float
    packed_bytes: int
    name: str = "polar_ultra_1bit_block2_r0"
    bits_per_fde_coordinate: float = 0.5


def _orthogonal_rotation(dimension: int, seed: int = 91) -> NDArray[np.float32]:
    rng = np.random.default_rng(seed + dimension)
    q, r = np.linalg.qr(rng.normal(size=(dimension, dimension)))
    q *= np.sign(np.diag(r))[None, :]
    return q.astype(np.float32)


def _fit_two_centers(values: NDArray[np.floating]) -> NDArray[np.float32]:
    flattened = np.asarray(values, np.float32).reshape(-1)
    if not len(flattened):
        raise ValueError("cannot train PolarQuant with no values")
    centers = np.quantile(flattened, [0.25, 0.75]).astype(np.float32)
    for _ in range(32):
        split = float(np.mean(centers))
        low, high = flattened[flattened <= split], flattened[flattened > split]
        updated = np.asarray(
            [
                low.mean() if len(low) else centers[0],
                high.mean() if len(high) else centers[1],
            ],
            np.float32,
        )
        if np.allclose(updated, centers):
            break
        centers = updated
    return np.sort(centers)


def train_polar(fdes: NDArray[np.floating]) -> tuple[PolarCodec, NDArray[np.uint8]]:
    values = np.asarray(fdes, np.float32)
    if values.ndim != 2 or not len(values) or values.shape[1] % 2:
        raise ValueError("PolarQuant needs a non-empty matrix with an even dimension")
    rotation = _orthogonal_rotation(2)
    blocks = values.reshape(len(values), -1, 2) @ rotation
    angles = np.arctan2(blocks[..., 1], blocks[..., 0])
    centers = _fit_two_centers(angles)
    boundary = float(np.mean(centers))
    packed = np.packbits((angles > boundary).astype(np.uint8), axis=1)
    radius = float(np.linalg.norm(blocks, axis=2).mean())
    codec = PolarCodec(
        dimension=int(values.shape[1]),
        angle_centers=(float(centers[0]), float(centers[1])),
        radius=radius,
        boundary=boundary,
        packed_bytes=int(packed.shape[1]),
    )
    return codec, packed


def encode_polar(fde: NDArray[np.floating], codec: PolarCodec) -> NDArray[np.uint8]:
    values = np.asarray(fde, np.float32).reshape(-1)
    if len(values) != codec.dimension:
        raise ValueError("FDE dimension does not match PolarQuant codec")
    blocks = values.reshape(-1, 2) @ _orthogonal_rotation(2)
    angles = np.arctan2(blocks[:, 1], blocks[:, 0])
    return np.packbits((angles > codec.boundary).astype(np.uint8))


def _byte_lookup(
    query_fde: NDArray[np.floating], codec: PolarCodec
) -> tuple[float, NDArray[np.float32]]:
    rotation = _orthogonal_rotation(2)
    centers = np.asarray(codec.angle_centers, np.float32)
    prototypes = (
        codec.radius * np.stack([np.cos(centers), np.sin(centers)], axis=1)
    ) @ rotation.T
    query_blocks = np.asarray(query_fde, np.float32).reshape(-1, 2)
    pair_lookup = query_blocks @ prototypes.T
    base = float(np.sum(pair_lookup[:, 0], dtype=np.float32))
    deltas = (pair_lookup[:, 1] - pair_lookup[:, 0]).reshape(-1, 8)
    byte_values = np.arange(256, dtype=np.uint16)
    shifts = np.arange(7, -1, -1, dtype=np.uint16)
    bits = ((byte_values[:, None] >> shifts) & 1).astype(np.float32)
    return base, deltas @ bits.T


def polar_scores(
    index: NDArray[np.uint8], query_fde: NDArray[np.floating], codec: PolarCodec
) -> NDArray[np.float32]:
    packed = np.asarray(index, np.uint8)
    if packed.ndim != 2 or packed.shape[1] != codec.packed_bytes:
        raise ValueError("packed index does not match PolarQuant codec")
    base, lookup = _byte_lookup(query_fde, codec)
    scores = np.full(len(packed), base, np.float32)
    for position in range(packed.shape[1]):
        scores += lookup[position, packed[:, position]]
    return scores
