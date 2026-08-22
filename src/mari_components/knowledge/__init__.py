"""Evidence-preserving model-output parsers and deterministic policies."""

from .answers import (
    AnswerDisposition,
    GroundedAnswer,
    parse_answer,
    parse_answer_candidates,
)
from .decisions import parse_decisions
from .excerpt import excerpt
from .facts import FactAssessment, parse_claim_assessments, parse_facts
from .freshness import (
    FreshnessReport,
    FreshnessStatus,
    RevisionChange,
    assess_freshness,
    evidence_dependencies,
)
from .glossary import parse_glossary
from .links import (
    DEFAULT_SIMILARITY_LIMIT,
    DEFAULT_SIMILARITY_THRESHOLD,
    LinkCandidate,
    derive_links,
    extract_explicit_links,
)
from .refinement import RefinementEdit, parse_refinement
from .scoring import grounding_coverage
from .summaries import (
    DigestSummary,
    DigestTopic,
    ImpactAssessment,
    parse_digest,
    parse_impact,
)
from .tags import (
    TagAssignments,
    TagDefinition,
    assign_tags,
    normalize_tag,
    search_weight,
)

__all__ = [
    "DEFAULT_SIMILARITY_LIMIT",
    "DEFAULT_SIMILARITY_THRESHOLD",
    "AnswerDisposition",
    "DigestSummary",
    "DigestTopic",
    "FactAssessment",
    "FreshnessReport",
    "FreshnessStatus",
    "GroundedAnswer",
    "ImpactAssessment",
    "LinkCandidate",
    "RefinementEdit",
    "RevisionChange",
    "TagAssignments",
    "TagDefinition",
    "assess_freshness",
    "assign_tags",
    "derive_links",
    "evidence_dependencies",
    "excerpt",
    "extract_explicit_links",
    "grounding_coverage",
    "parse_answer",
    "parse_answer_candidates",
    "parse_claim_assessments",
    "parse_decisions",
    "parse_digest",
    "parse_facts",
    "parse_glossary",
    "parse_impact",
    "parse_refinement",
    "normalize_tag",
    "search_weight",
]
