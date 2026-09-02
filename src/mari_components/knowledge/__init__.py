"""Evidence-preserving model-output parsers and deterministic policies."""

from .answers import (
    AnswerDisposition,
    GroundedAnswer,
    parse_answer,
    parse_answer_candidates,
)
from .decisions import parse_decisions
from .excerpt import excerpt
from .fact_scans import fact_scan_revisions, pending_fact_sections
from .facts import (
    FactAssessment,
    deduplicate_fact_candidates,
    normalize_claim,
    parse_claim_assessments,
    parse_facts,
)
from .freshness import (
    FreshnessReport,
    FreshnessStatus,
    KnowledgeDependency,
    RevisionChange,
    assess_dependencies,
    assess_freshness,
    evidence_dependencies,
    impacted_artifacts,
)
from .glossary import parse_glossary
from .links import (
    DEFAULT_SIMILARITY_LIMIT,
    DEFAULT_SIMILARITY_THRESHOLD,
    LinkCandidate,
    derive_links,
    extract_explicit_links,
)
from .mutations import (
    MemoryDecision,
    MemoryMutation,
    MemoryMutationPlan,
    MemoryOperation,
    apply_memory_mutations,
    plan_memory_mutations,
)
from .refinement import RefinementEdit, parse_refinement
from .research import (
    MemorySignal,
    NoteEvolutionPlan,
    SalientMemory,
    plan_note_evolution,
    rank_salient_memories,
)
from .scoring import grounding_coverage
from .sections import document_sections, section_revisions
from .segmentation import TopicSegment, hybrid_topic_segments
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
    "KnowledgeDependency",
    "ImpactAssessment",
    "LinkCandidate",
    "MemoryDecision",
    "MemoryMutation",
    "MemoryMutationPlan",
    "MemoryOperation",
    "MemorySignal",
    "NoteEvolutionPlan",
    "RefinementEdit",
    "RevisionChange",
    "SalientMemory",
    "TagAssignments",
    "TagDefinition",
    "TopicSegment",
    "apply_memory_mutations",
    "assess_dependencies",
    "assess_freshness",
    "assign_tags",
    "derive_links",
    "deduplicate_fact_candidates",
    "document_sections",
    "evidence_dependencies",
    "excerpt",
    "extract_explicit_links",
    "fact_scan_revisions",
    "grounding_coverage",
    "hybrid_topic_segments",
    "impacted_artifacts",
    "normalize_claim",
    "parse_answer",
    "parse_answer_candidates",
    "parse_claim_assessments",
    "parse_decisions",
    "parse_digest",
    "parse_facts",
    "parse_glossary",
    "parse_impact",
    "parse_refinement",
    "plan_memory_mutations",
    "plan_note_evolution",
    "pending_fact_sections",
    "rank_salient_memories",
    "normalize_tag",
    "search_weight",
    "section_revisions",
]
