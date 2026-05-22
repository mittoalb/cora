"""The `UpdateMethodParametersSchema` command — intent dataclass for this slice.

Operators set, replace, or clear the JSON Schema declaring
the shape of parameter dicts that downstream Plans (6g-b) and Runs
(6g-c) carry for this Method. Independent of the Defined / Versioned
/ Deprecated content lifecycle: schema iteration is its own audit
stream.

`parameters_schema=None` is a valid intent (clear the schema). The
decider validates well-formedness via
`parameters_validation.validate_parameters_schema` before emitting
`MethodParametersSchemaUpdated`. See [[project_run_parameters_design]]
memory for the locked subset + 6g-a/b/c family layout.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class UpdateMethodParametersSchema:
    """Set / replace / clear a Method's parameters_schema."""

    method_id: UUID
    parameters_schema: dict[str, Any] | None
