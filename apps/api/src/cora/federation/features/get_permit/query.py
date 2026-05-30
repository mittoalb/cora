"""The `GetPermit` query: intent dataclass for the read slice.

Mirrors `GetCalibration` / `GetCaution`: queries are dataclasses just
like commands, naming the read intent and carrying only what the
caller controls. The application handler adds context (correlation_id,
principal_id) at call time.
"""

from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class GetPermit:
    """Read the current state of an existing Permit by id."""

    permit_id: UUID


class GetPermitRequest(BaseModel):
    """Wire shape for the `get_permit` request (REST path + MCP arg)."""

    permit_id: UUID = Field(..., description="Target permit's id.")

    model_config = {"extra": "forbid"}
