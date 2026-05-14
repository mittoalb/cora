"""The `UpdatePlanDefaultParameters` command — intent dataclass for this slice.

Phase 6g-b. `plan_id` is the target Plan aggregate.
`default_parameters_patch` is a dict applied to current
`default_parameters` via RFC 7396 (JSON Merge Patch) semantics:
keys with non-null values are set/replaced; keys with null are
deleted; absent keys are preserved.

Validation runs at the handler boundary against the owning
Method's `parameters_schema` (loaded by the handler before
reaching the decider). Permissive when Method declares no schema
(see [[project_run_parameters_design]] §6g-b).
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class UpdatePlanDefaultParameters:
    """Update a Plan's default_parameters dict with RFC 7396 merge semantics."""

    plan_id: UUID
    default_parameters_patch: dict[str, Any]
