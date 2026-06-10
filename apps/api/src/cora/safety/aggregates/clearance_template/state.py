"""ClearanceTemplate aggregate state, status enum, errors, and value objects.

`ClearanceTemplate` defines reusable form templates for safety clearances.
Template-tier aggregate emits "Defined" genesis events (not "Registered");
the genesis event type is `ClearanceTemplateDefined`.

Status FSM: `Draft -> Active -> Deprecated -> Withdrawn`.
Four closed enum values locked day one per [[project_slice9_design]].

Facility-scoped uniqueness on `(facility_code, code)` via projection
PARTIAL UNIQUE INDEX `WHERE status != 'Withdrawn'`.

Version field ships day-one in the dataclass (default 1) + supersedes_template_id
for version tracking; the version-bump event ships in 9B.

## Status as enum-in-state, derived-from-event-type-in-evolver

`ClearanceTemplateStatus` is a `StrEnum` (like FamilyStatus, SubjectStatus).
State holds the enum; evolver derives status from event type
(ClearanceTemplateDefined -> Draft).

## Day-one field structure

ClearanceTemplate carries version + supersedes_template_id fields day one
so the schema does not churn when 9B ships the version-bump event.
Both ship in the ClearanceTemplateDefined payload.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from cora.safety.aggregates.clearance_template._value_types import (
    ClearanceTemplateCode,
    ClearanceTemplateTitle,
    ClearanceTemplateVersion,
)
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId


class ClearanceTemplateStatus(StrEnum):
    """The ClearanceTemplate's lifecycle state.

    Four values locked day one per [[project_slice9_design]]:

      - `Draft`       -- newly defined, not yet activated
      - `Active`      -- in use; can be referenced by new Clearances
      - `Deprecated`  -- no longer recommended; existing Clearances unaffected
      - `Withdrawn`   -- completely removed from the address space

    Transitions:
      - Draft -> Active         (activate_clearance_template; 9B)
      - Active -> Deprecated    (deprecate_clearance_template; 9C)
      - (any non-terminal) -> Withdrawn (withdraw_clearance_template; 9C)

    `Draft` is the genesis state set by `define_clearance_template`. The enum
    values are PascalCase strings (matching the BC-map status vocabulary) so
    log lines and DTOs read naturally without additional mapping.
    """

    DRAFT = "Draft"
    ACTIVE = "Active"
    DEPRECATED = "Deprecated"
    WITHDRAWN = "Withdrawn"


class ClearanceTemplateAlreadyExistsError(Exception):
    """Attempted to define a template whose stream already has events."""

    def __init__(self, template_id: UUID) -> None:
        super().__init__(f"ClearanceTemplate {template_id} already exists")
        self.template_id = template_id


class ClearanceTemplateNotFoundError(Exception):
    """Attempted an operation on a template whose stream has no events."""

    def __init__(self, template_id: UUID) -> None:
        super().__init__(f"ClearanceTemplate {template_id} not found")
        self.template_id = template_id


class ClearanceTemplateFacilityNotFoundError(Exception):
    """The facility referenced by the template does not exist."""

    def __init__(self, facility_code: FacilityCode) -> None:
        super().__init__(f"Facility {facility_code.value} not found")
        self.facility_code = facility_code


class ClearanceTemplateCannotActivateError(Exception):
    """Attempted `activate_clearance_template` from a disqualifying status.

    Activation is locked to Draft per [[project_slice9_design]] L2; any other
    starting status raises this strict-not-idempotent error.
    """

    def __init__(self, template_id: UUID, current_status: ClearanceTemplateStatus) -> None:
        super().__init__(
            f"ClearanceTemplate {template_id} cannot be activated: currently in status "
            f"{current_status.value}, activate_clearance_template requires "
            f"{ClearanceTemplateStatus.DRAFT.value}"
        )
        self.template_id = template_id
        self.current_status = current_status


class ClearanceTemplateCannotVersionError(Exception):
    """Attempted `version_clearance_template` from a disqualifying status.

    Version bumps are additive within Active per [[project_slice9_design]] L4;
    Draft/Deprecated/Withdrawn parents are not eligible.
    """

    def __init__(self, template_id: UUID, current_status: ClearanceTemplateStatus) -> None:
        super().__init__(
            f"ClearanceTemplate {template_id} cannot be versioned: currently in status "
            f"{current_status.value}, version_clearance_template requires "
            f"{ClearanceTemplateStatus.ACTIVE.value}"
        )
        self.template_id = template_id
        self.current_status = current_status


class ClearanceTemplateFacilityMismatchError(Exception):
    """A version-chain parent belongs to a different facility than the child.

    Enforces the cross-facility identity lock per [[project_slice9_design]] L5:
    a template's supersedes lineage stays within one facility's scope.
    """

    def __init__(
        self,
        template_id: UUID,
        template_facility_code: FacilityCode,
        parent_facility_code: FacilityCode,
    ) -> None:
        super().__init__(
            f"ClearanceTemplate {template_id} (facility {template_facility_code.value}) "
            f"cannot supersede a parent in facility {parent_facility_code.value}: "
            "version chains are same-facility-scoped"
        )
        self.template_id = template_id
        self.template_facility_code = template_facility_code
        self.parent_facility_code = parent_facility_code


@dataclass(frozen=True)
class ClearanceTemplate:
    """Aggregate root: a reusable clearance form template definition.

    `id` is the stable opaque PK (UUID).
    `facility_code` is the facility this template belongs to.
    `code` is the machine-readable identifier (facility-scoped).
    `title` is the human-readable display name.
    `status` is the lifecycle state (Draft | Active | Deprecated | Withdrawn).
    `version` is the current version number (default 1).
    `supersedes_template_id` tracks version lineage (None until first version bump).
    `external_ref` is an optional external system reference.
    """

    id: UUID
    facility_code: FacilityCode
    code: ClearanceTemplateCode
    title: ClearanceTemplateTitle
    defined_at: datetime
    defined_by: ActorId
    status: ClearanceTemplateStatus = ClearanceTemplateStatus.DRAFT
    version: ClearanceTemplateVersion = field(default_factory=lambda: ClearanceTemplateVersion(1))
    supersedes_template_id: UUID | None = None
    external_ref: str | None = None
