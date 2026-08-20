"""Data-oblivious MUVERA fixed-dimensional encodings."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


FloatArray = NDArray[np.float32]


@dataclass(frozen=True, slots=True)
class FDEConfig:
    repetitions: int = 20
    simhash_bits: int = 5
    projection_dimension: int = 8
    seed: int = 1
    fill_empty_partitions: bool = True

    def __post_init__(self) -> None:
        if self.repetitions < 1:
            raise ValueError("repetitions must be positive")
        if not 1 <= self.simhash_bits <= 16:
            raise ValueError("simhash_bits must be between 1 and 16")
        if self.projection_dimension < 1:
            raise ValueError("projection_dimension must be positive")

    @property
    def partitions(self) -> int:
        return 1 << self.simhash_bits

    @property
    def dimension(self) -> int:
        return self.repetitions * self.partitions * self.projection_dimension


ProjectionParameters = tuple[tuple[FloatArray, FloatArray], ...]


def projection_parameters(config: FDEConfig, input_dimension: int) -> ProjectionParameters:
    if input_dimension < 1:
        raise ValueError("input_dimension must be positive")
    output: list[tuple[FloatArray, FloatArray]] = []
    for repetition in range(config.repetitions):
        rng = np.random.default_rng(config.seed + repetition)
        simhash = rng.normal(size=(input_dimension, config.simhash_bits)).astype(np.float32)
        destinations = rng.integers(0, config.projection_dimension, size=input_dimension)
        signs = rng.choice(np.asarray([-1.0, 1.0], np.float32), size=input_dimension)
        projection = np.zeros((input_dimension, config.projection_dimension), np.float32)
        projection[np.arange(input_dimension), destinations] = signs
        output.append((simhash, projection))
    return tuple(output)


def _gray_partition(bits: NDArray[np.bool_]) -> NDArray[np.int32]:
    index = np.zeros(len(bits), np.int32)
    for column in range(bits.shape[1]):
        index = (index << 1) + np.logical_xor(bits[:, column], index & 1)
    return index


def _partition_bits(partitions: int, width: int) -> NDArray[np.bool_]:
    gray = np.arange(partitions, dtype=np.int32)
    binary = np.bitwise_xor(gray, gray >> 1)
    shifts = np.arange(width - 1, -1, -1, dtype=np.int32)
    return ((binary[:, None] >> shifts[None, :]) & 1).astype(bool)


def encode_fde(
    points: NDArray[np.floating],
    config: FDEConfig,
    parameters: ProjectionParameters | None = None,
    *,
    query: bool,
) -> FloatArray:
    """Encode query points by sum and document points by partition centroid."""
    values = np.asarray(points, np.float32)
    if values.ndim != 2 or not len(values) or values.shape[1] < 1:
        raise ValueError("MUVERA needs a non-empty two-dimensional vector matrix")
    params = parameters or projection_parameters(config, int(values.shape[1]))
    if len(params) != config.repetitions:
        raise ValueError("projection parameters do not match repetitions")
    output = np.zeros(
        (config.repetitions, config.partitions, config.projection_dimension), np.float32
    )
    target_bits = _partition_bits(config.partitions, config.simhash_bits)
    for repetition, (simhash, projection) in enumerate(params):
        if simhash.shape[0] != values.shape[1] or projection.shape[0] != values.shape[1]:
            raise ValueError("projection parameters do not match input dimension")
        signs = values @ simhash > 0
        buckets = _gray_partition(signs)
        projected = values @ projection
        np.add.at(output[repetition], buckets, projected)
        if query:
            continue
        counts = np.bincount(buckets, minlength=config.partitions)
        occupied = counts > 0
        output[repetition, occupied] /= counts[occupied, None]
        if config.fill_empty_partitions and np.any(~occupied):
            for bucket in np.flatnonzero(~occupied):
                nearest = int(np.argmin(np.count_nonzero(signs != target_bits[bucket], axis=1)))
                output[repetition, bucket] = projected[nearest]
    return output.reshape(-1)
