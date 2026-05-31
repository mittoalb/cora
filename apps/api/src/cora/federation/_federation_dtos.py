"""Shared Pydantic DTOs for the Federation wire shape.

BC-level scaffolding shared across slice routes / MCP tools. Hoisted
to the BC level so future slices reuse the same wire shape without
cross-slice imports (the cross-slice-independence architecture
fitness function would otherwise reject the import).

Naming: leading underscore on the filename marks this as BC-private
(not part of the public API surface); contained classes are
public-within-the-BC so importing slices reference them without the
underscore (`FederationErrorDTO`, etc.).

This module holds only the shared error DTO. Per-aggregate input /
output DTOs (Permit terms-union, Credential rotation pointers, Seal
pointer-sign body) live with their owning slices.
"""

from pydantic import BaseModel, Field


class FederationErrorDTO(BaseModel):
    """Wire shape for Federation BC error responses."""

    detail: str = Field(
        ...,
        description="Human-readable error reason.",
    )


__all__ = ["FederationErrorDTO"]
