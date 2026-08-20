"""Provisional storage-neutral byte serialization for immutable indexes."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import io
import json
from typing import Mapping

import numpy as np

from .index import MuveraIndex
from .muvera import FDEConfig
from .polarquant import PolarCodec


FORMAT_VERSION = 1
ARRAY_FILES = ("offsets.npy", "vectors.npy", "polar.npy")


def _array_bytes(value: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    np.save(buffer, value, allow_pickle=False)
    return buffer.getvalue()


def serialize_index(index: MuveraIndex) -> Mapping[str, bytes]:
    metadata = {
        "version": FORMAT_VERSION,
        "document_ids": list(index.document_ids),
        "input_dimension": index.input_dimension,
        "config": asdict(index.config),
        "codec": asdict(index.codec),
        "hashes": dict(index.hashes),
    }
    files = {
        "metadata.json": json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode(),
        "offsets.npy": _array_bytes(index.offsets),
        "vectors.npy": _array_bytes(index.vectors),
        "polar.npy": _array_bytes(index.packed),
    }
    manifest = {
        "version": FORMAT_VERSION,
        "files": {name: hashlib.sha256(body).hexdigest() for name, body in files.items()},
    }
    return {
        **files,
        "manifest.json": json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode(),
    }


def deserialize_index(files: Mapping[str, bytes]) -> MuveraIndex:
    expected = {"manifest.json", "metadata.json", *ARRAY_FILES}
    if set(files) != expected:
        raise ValueError("index files are incomplete or contain unknown entries")
    try:
        manifest = json.loads(files["manifest.json"])
        metadata = json.loads(files["metadata.json"])
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid index JSON") from error
    if manifest.get("version") != FORMAT_VERSION or metadata.get("version") != FORMAT_VERSION:
        raise ValueError("unsupported index format version")
    checksums = manifest.get("files")
    if not isinstance(checksums, dict) or set(checksums) != expected - {"manifest.json"}:
        raise ValueError("invalid index manifest")
    for name, expected_digest in checksums.items():
        if hashlib.sha256(files[name]).hexdigest() != expected_digest:
            raise ValueError(f"checksum mismatch for {name}")
    try:
        offsets = np.load(io.BytesIO(files["offsets.npy"]), allow_pickle=False)
        vectors = np.load(io.BytesIO(files["vectors.npy"]), allow_pickle=False)
        packed = np.load(io.BytesIO(files["polar.npy"]), allow_pickle=False)
        config = FDEConfig(**metadata["config"])
        codec = PolarCodec(**metadata["codec"])
        document_ids = tuple(str(value) for value in metadata["document_ids"])
        hashes = {str(key): str(value) for key, value in metadata.get("hashes", {}).items()}
        input_dimension = int(metadata["input_dimension"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("invalid index metadata or arrays") from error
    return MuveraIndex(
        document_ids, offsets, vectors, packed, codec, config, input_dimension, hashes
    )
