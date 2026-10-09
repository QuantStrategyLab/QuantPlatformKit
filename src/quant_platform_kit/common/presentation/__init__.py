"""Presentation helpers for strategy/execution contracts.

Display layout and dashboard copy belong here (or call sites), not in the
pure execution planning API. Compatibility facades may still emit legacy
payloads that mix both concerns.
"""

from .value_target_plan import (
    ValueTargetDisplayAnnotations,
    ValueTargetExecutionSemantics,
    ValueTargetPlanPresentation,
    display_annotations_from_execution_annotations,
    execution_semantics_from_annotations,
    merge_value_target_execution_annotations,
)

__all__ = [
    "ValueTargetDisplayAnnotations",
    "ValueTargetExecutionSemantics",
    "ValueTargetPlanPresentation",
    "display_annotations_from_execution_annotations",
    "execution_semantics_from_annotations",
    "merge_value_target_execution_annotations",
]
