"""The `AddAssetFamily` command — intent dataclass for this slice.

Family mutation: incremental add (single capability per call).
The slice is a sibling of `remove_asset_family`. Operators add
a Family to an Asset when commissioning a new technique on that
asset; remove when retiring one.

`asset_id` is the **target** Asset aggregate. `family_id` is the
Family being added; the decider does NOT verify it refers to a
real Family stream (eventual-consistency stance, same precedent
as Asset parent refs in 5b and Method.needed_families in 6a).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AddAssetFamily:
    """Add a Family to an existing asset's capability set."""

    asset_id: UUID
    family_id: UUID
