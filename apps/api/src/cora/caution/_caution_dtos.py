"""Shared Pydantic discriminated-union DTOs for the Caution wire shape.

BC-level scaffolding consumed by every slice that builds a Caution
from JSON request bodies / MCP tool args: today `register_caution`
(creates a new caution) and `supersede_caution` (creates the child of
a supersession). Hoisted to the BC level so the slices don't reach
across each other (the cross-slice-independence architecture
fitness function would otherwise reject the import).

Naming: leading underscore on the filename marks this as BC-private
(not part of the public API surface); the contained class + function
names are public-within-the-BC so importing slices reference them
without the underscore (`TargetDTO`, `target_from_dto`, etc.).

Mirrors `cora.safety._clearance_dtos` shape for the discriminated
target. Day-1 lock: two variants (`Asset`, `Procedure`); future
`Run` / `Subject` variants land additively when triggers fire.
"""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from cora.caution.aggregates.caution import (
    AssetTarget,
    CautionTarget,
    ProcedureTarget,
)


class TargetAssetDTO(BaseModel):
    """Wire shape for an Asset-targeted caution."""

    kind: Literal["Asset"]
    id: UUID = Field(..., description="Target Asset's id.")


class TargetProcedureDTO(BaseModel):
    """Wire shape for a Procedure-targeted caution."""

    kind: Literal["Procedure"]
    id: UUID = Field(..., description="Target Procedure's id.")


TargetDTO = Annotated[
    TargetAssetDTO | TargetProcedureDTO,
    Field(discriminator="kind"),
]


def target_from_dto(dto: TargetDTO) -> CautionTarget:
    """Convert a wire-shape TargetDTO into the typed domain CautionTarget VO."""
    if isinstance(dto, TargetAssetDTO):
        return AssetTarget(asset_id=dto.id)
    return ProcedureTarget(procedure_id=dto.id)


__all__ = [
    "TargetAssetDTO",
    "TargetDTO",
    "TargetProcedureDTO",
    "target_from_dto",
]
