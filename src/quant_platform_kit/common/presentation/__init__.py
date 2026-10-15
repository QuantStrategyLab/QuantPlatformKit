"""Presentation helpers for strategy/execution contracts.

Display layout and dashboard copy belong here (or call sites), not in the
pure execution planning API. Compatibility facades may still emit legacy
payloads that mix both concerns.
"""

from .value_target_plan import (
    VALUE_TARGET_DISPLAY_FIELD_NAMES,
    ValueTargetDisplayAnnotations,
    ValueTargetExecutionSemantics,
    ValueTargetPlanPresentation,
    display_annotations_from_execution_annotations,
    execution_semantics_from_annotations,
    merge_value_target_execution_annotations,
    resolve_value_target_execution_annotations,
    split_value_target_annotation_parts,
)

__all__ = [
    "VALUE_TARGET_DISPLAY_FIELD_NAMES",
    "ValueTargetDisplayAnnotations",
    "ValueTargetExecutionSemantics",
    "ValueTargetPlanPresentation",
    "display_annotations_from_execution_annotations",
    "execution_semantics_from_annotations",
    "merge_value_target_execution_annotations",
    "resolve_value_target_execution_annotations",
    "split_value_target_annotation_parts",
]
