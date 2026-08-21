"""Privacy-bounded trajectory normalization, segmentation, and mining."""

from .mine import TrajectoryAnalysis, analyze_trajectory
from .normalize import DEFAULT_FAMILY_MAP, TrajectoryStep, normalize_steps
from .segment import TrajectoryPhase, rework_count, segment_phases
from .workflows import DistilledWorkflow, WorkflowMatch, distill_workflows, match_workflow
from .hierarchy import HierarchyMatch, cosine, match_hierarchy, project_embeddings_2d

__all__ = [
    "DEFAULT_FAMILY_MAP",
    "TrajectoryAnalysis",
    "DistilledWorkflow",
    "TrajectoryPhase",
    "TrajectoryStep",
    "WorkflowMatch",
    "HierarchyMatch",
    "analyze_trajectory",
    "distill_workflows",
    "match_workflow",
    "match_hierarchy",
    "project_embeddings_2d",
    "cosine",
    "normalize_steps",
    "rework_count",
    "segment_phases",
]
