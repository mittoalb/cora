"""The `AddAssetPort` command — intent dataclass for this slice.

`asset_id` is the target Asset aggregate. `port_name` is the
operator-supplied port name (must be unique within the Asset's
ports). `direction` is INPUT or OUTPUT (PortDirection enum).
`signal_type` is operator-supplied free text (`"TTL"`, `"LVDS"`,
`"Encoder"`, `"Network"`, `"Sync"`, etc).
"""

from dataclasses import dataclass
from uuid import UUID

from cora.equipment.aggregates.asset.state import PortDirection


@dataclass(frozen=True)
class AddAssetPort:
    """Add a typed port to an existing Asset's port set."""

    asset_id: UUID
    port_name: str
    direction: PortDirection
    signal_type: str
