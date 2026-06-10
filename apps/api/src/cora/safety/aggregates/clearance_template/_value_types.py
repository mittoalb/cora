"""ClearanceTemplate aggregate value objects and errors.

ClearanceTemplateId is a NewType UUID identifying a template stream in the
event store. ClearanceTemplateCode and ClearanceTemplateTitle are trimmed-
bounded-name VOs following the FamilyName and AssetName pattern. ClearanceTemplateVersion
is a frozen dataclass wrapping a positive int.

See [[project_slice9_design]] L1, L3, L4 for template-aggregate design.
"""

from dataclasses import dataclass
from typing import NewType
from uuid import UUID

from cora.shared.bounded_text import bounded_name

ClearanceTemplateId = NewType("ClearanceTemplateId", UUID)
"""UUID that identifies a ClearanceTemplate stream in the event store."""

CLEARANCE_TEMPLATE_CODE_MAX_LENGTH = 50
"""Max length (inclusive) for `ClearanceTemplateCode.value` after trim."""

CLEARANCE_TEMPLATE_TITLE_MAX_LENGTH = 200
"""Max length (inclusive) for `ClearanceTemplateTitle.value` after trim."""

CLEARANCE_TEMPLATE_EXTERNAL_REF_MAX_LENGTH = 500
"""Max length (inclusive) for the optional `external_ref` field."""


class InvalidClearanceTemplateCodeError(ValueError):
    """The supplied code is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"ClearanceTemplate code must be 1-{CLEARANCE_TEMPLATE_CODE_MAX_LENGTH} "
            f"chars after trimming (got: {value!r})"
        )
        self.value = value


class InvalidClearanceTemplateTitleError(ValueError):
    """The supplied title is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"ClearanceTemplate title must be 1-{CLEARANCE_TEMPLATE_TITLE_MAX_LENGTH} "
            f"chars after trimming (got: {value!r})"
        )
        self.value = value


class InvalidClearanceTemplateVersionError(ValueError):
    """The supplied version is not a positive integer."""

    def __init__(self, value: int) -> None:
        super().__init__(f"ClearanceTemplate version must be a positive integer (got: {value!r})")
        self.value = value


@bounded_name(
    max_length=CLEARANCE_TEMPLATE_CODE_MAX_LENGTH,
    error_class=InvalidClearanceTemplateCodeError,
)
@dataclass(frozen=True)
class ClearanceTemplateCode:
    """Template code identifier. Trimmed; 1-50 chars."""

    value: str


@bounded_name(
    max_length=CLEARANCE_TEMPLATE_TITLE_MAX_LENGTH,
    error_class=InvalidClearanceTemplateTitleError,
)
@dataclass(frozen=True)
class ClearanceTemplateTitle:
    """Template display title. Trimmed; 1-200 chars."""

    value: str


@dataclass(frozen=True)
class ClearanceTemplateVersion:
    """Mutable template version number: positive integer.

    Day-one field per [[project_slice9_design]] L4. Version-bump events
    ship in 9B; 9A includes the FIELDS so the schema doesn't churn.
    """

    value: int

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise InvalidClearanceTemplateVersionError(self.value)


__all__ = [
    "CLEARANCE_TEMPLATE_CODE_MAX_LENGTH",
    "CLEARANCE_TEMPLATE_EXTERNAL_REF_MAX_LENGTH",
    "CLEARANCE_TEMPLATE_TITLE_MAX_LENGTH",
    "ClearanceTemplateCode",
    "ClearanceTemplateId",
    "ClearanceTemplateTitle",
    "ClearanceTemplateVersion",
    "InvalidClearanceTemplateCodeError",
    "InvalidClearanceTemplateTitleError",
    "InvalidClearanceTemplateVersionError",
]
