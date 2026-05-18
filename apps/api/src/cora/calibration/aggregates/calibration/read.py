"""Read repository for the Calibration aggregate.

`load_calibration(event_store, calibration_id) -> Calibration | None`
mirrors `load_caution` / `load_clearance` / `load_asset`. Used by the
`get_calibration` query slice and the `append_revision` handler (which
pre-loads the target Calibration before the decider).
"""

from uuid import UUID

from cora.calibration.aggregates.calibration.events import from_stored
from cora.calibration.aggregates.calibration.evolver import fold
from cora.calibration.aggregates.calibration.state import Calibration
from cora.infrastructure.ports import EventStore

_STREAM_TYPE = "Calibration"


async def load_calibration(event_store: EventStore, calibration_id: UUID) -> Calibration | None:
    """Load and fold a Calibration's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, calibration_id)
    events = [from_stored(s) for s in stored]
    return fold(events)
