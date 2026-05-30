"""Drawing value object: a typed reference to an engineering drawing.

A `Drawing` is a structured pointer to a document in some external
document-management system, not the document itself. Engineering
drawings travel as a triple of `(system, number, revision)` per ISO
7200 title-block convention, CFIHOS handover specs, and every PLM /
EDMS in the corpus (Teamcenter Dataset, Documentum, ICMS, ...).

Storing the system separately from the number means CORA can hold
references across facilities without assuming a single document
registry: APS uses ICMS; MAX IV will use something else; PIDINST
mints DOIs.

Revision is optional. `revision = None` means "resolves to latest"
(ISO 7200 / DOI / EDMS default-resolution semantics). When present,
the Drawing references a specific snapshot. Whether a facility's
adapter actually exposes latest-resolution is a per-adapter contract
(Watch item: ICMS latest-resolution semantics need adapter
confirmation before the first revision-less Drawing is registered).

`Drawing` is a closed-shape frozen dataclass. NOT
`json_schema_validation` (that pattern is for declarer-owns-schema /
carrier-owns-dict); validation lives in field shape + enum
membership + `validate_bounded_text` from
`cora.infrastructure.bounded_text` (the 22nd hoisting site for the
trim + length-check + raise pattern; AssetPort precedent uses
per-field error classes).

`DrawingSystem` is an extensible StrEnum (registry of accepted
systems enforced per-facility at the adapter boundary, NOT in the
VO).

Used as an optional field on both `Mount` (where the slot is in the
beamline) and `Asset` (what the specimen was built to). The two are
different documents; do NOT collapse them.

Promote to a full `Document` BC only when drawings need their own
lifecycle (review status, supersedes-chain, ECO propagation per
MIL-HDBK-61A 5.4 / CMII, ACL).
"""

from dataclasses import dataclass
from enum import StrEnum

from cora.equipment.errors import (
    InvalidDrawingNumberError,
    InvalidDrawingRevisionError,
)
from cora.infrastructure.bounded_text import validate_bounded_text

# Keep the literal length caps in errors.py message templates in sync
# with these constants. The errors live in errors.py (architecture
# fitness), the constants live here (used both by VO validation and
# by tests), and the two cannot trivially share without a circular
# import (errors -> _drawing -> errors). Drift risk is small; v1 lock.
DRAWING_NUMBER_MAX_LENGTH = 200
DRAWING_REVISION_MAX_LENGTH = 100


class DrawingSystem(StrEnum):
    """The external document-management system a Drawing lives in.

    Extensible StrEnum: v1 ships with three known systems but new
    facilities add their own. Whether a given system value is
    actually wired to an adapter is enforced per-facility at the
    adapter boundary, NOT here.

      - `ICMS`: APS Information Content Management System (Documentum-
        backed).
      - `EDMS`: generic Engineering Document Management System
        (CERN EDMS and similar).
      - `DOI`: DataCite Digital Object Identifier (used by PIDINST
        for instrument-level identifiers).
    """

    ICMS = "ICMS"
    EDMS = "EDMS"
    DOI = "DOI"


@dataclass(frozen=True)
class Drawing:
    """A typed reference to an engineering drawing in an external system.

    `system` says which document registry; `number` is the document
    identifier within that registry; `revision` is the optional
    snapshot pin (None means "latest").

    Equality and hash are structural across the three fields, so two
    Drawing instances referring to the same `(system, number, revision)`
    triple collapse in a set.
    """

    system: DrawingSystem
    number: str
    revision: str | None = None

    def __post_init__(self) -> None:
        trimmed_number = validate_bounded_text(
            self.number,
            max_length=DRAWING_NUMBER_MAX_LENGTH,
            error_class=InvalidDrawingNumberError,
        )
        object.__setattr__(self, "number", trimmed_number)

        if self.revision is not None:
            trimmed_revision = validate_bounded_text(
                self.revision,
                max_length=DRAWING_REVISION_MAX_LENGTH,
                error_class=InvalidDrawingRevisionError,
            )
            object.__setattr__(self, "revision", trimmed_revision)


__all__ = [
    "DRAWING_NUMBER_MAX_LENGTH",
    "DRAWING_REVISION_MAX_LENGTH",
    "Drawing",
    "DrawingSystem",
]
