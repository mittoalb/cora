"""Read repository for the Mount aggregate.

`load_mount(event_store, mount_id) -> Mount | None` mirrors
`load_frame` / `load_asset`. Used by update-style commands
(`update_mount_placement`, `install_asset`, `uninstall_asset`,
`decommission_mount`) that need to load + fold before deciding.
"""

from uuid import UUID

from cora.equipment.aggregates.mount.events import from_stored
from cora.equipment.aggregates.mount.evolver import fold
from cora.equipment.aggregates.mount.state import Mount
from cora.infrastructure.ports import EventStore

_STREAM_TYPE = "Mount"


async def load_mount(event_store: EventStore, mount_id: UUID) -> Mount | None:
    """Load and fold a Mount's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, mount_id)
    events = [from_stored(s) for s in stored]
    return fold(events)
