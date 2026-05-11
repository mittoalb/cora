"""The `RegisterAsset` command — intent dataclass for this slice.

Carries the caller-controlled fields: the asset's display name,
its hierarchical level, and its parent_id (None only for
Enterprise-level roots — enforced by the decider). Server-side
concerns (new aggregate id, wall-clock timestamp, correlation id,
per-event ids) are injected by the handler from infrastructure
ports, matching the cross-BC create-style command shape locked in
Access / Trust / Subject / Equipment.

`level` is typed as `AssetLevel` (the StrEnum) so callers cannot
pass an invalid value; the route's Pydantic body and the MCP
tool's argument schema both enforce this at the API boundary.

`parent_id` is `UUID | None` — required for non-Enterprise
levels, must be null for Enterprise. Eventual-consistency stance
for the parent ref: the decider does NOT verify the referenced
parent Asset exists in the event store (same precedent as Trust's
Conduit zone refs).
"""

from dataclasses import dataclass
from uuid import UUID

from cora.equipment.aggregates.asset import AssetLevel


@dataclass(frozen=True)
class RegisterAsset:
    """Register a new asset with the given name, level, and parent."""

    name: str
    level: AssetLevel
    parent_id: UUID | None
