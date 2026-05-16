"""The `AddAssetCapability` command — intent dataclass for this slice.

Capability mutation: incremental add (single capability per call).
The slice is a sibling of `remove_asset_capability`. Operators add
a Capability to an Asset when commissioning a new technique on that
asset; remove when retiring one.

`asset_id` is the **target** Asset aggregate. `capability_id` is the
Capability being added; the decider does NOT verify it refers to a
real Capability stream (eventual-consistency stance, same precedent
as Asset parent refs in 5b and Method.needed_capabilities in 6a).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AddAssetCapability:
    """Add a Capability to an existing asset's capability set."""

    asset_id: UUID
    capability_id: UUID
