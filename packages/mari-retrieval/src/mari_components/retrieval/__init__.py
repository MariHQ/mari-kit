"""MUVERA candidate generation, PolarQuant compression, and exact reranking."""

from .index import MuveraIndex, RetrievalHit, build_index, search_index
from .maxsim import exact_maxsim
from .muvera import FDEConfig, encode_fde, projection_parameters
from .polarquant import PolarCodec, encode_polar, polar_scores, train_polar
from .query import keyword_score
from .serialization import deserialize_index, serialize_index
from .text import chunk_text, content_hash, title_from_markdown

__all__ = [
    "FDEConfig",
    "MuveraIndex",
    "PolarCodec",
    "RetrievalHit",
    "build_index",
    "chunk_text",
    "content_hash",
    "deserialize_index",
    "encode_fde",
    "encode_polar",
    "exact_maxsim",
    "keyword_score",
    "polar_scores",
    "projection_parameters",
    "search_index",
    "serialize_index",
    "train_polar",
    "title_from_markdown",
]
