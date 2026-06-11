"""Read repository for the Attestation aggregate.

``load_attestation(event_store, attestation_id) -> Attestation | None``
mirrors ``load_distribution`` and the other single-aggregate
fold-on-read helpers. List / filter / search across Attestations goes
through the ``proj_data_attestation_summary`` projection, not this
read repo.
"""

from uuid import UUID

from cora.data.aggregates.attestation.events import from_stored
from cora.data.aggregates.attestation.evolver import fold
from cora.data.aggregates.attestation.state import Attestation
from cora.infrastructure.ports import EventStore

_STREAM_TYPE = "Attestation"


async def load_attestation(event_store: EventStore, attestation_id: UUID) -> Attestation | None:
    """Load and fold an Attestation's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, attestation_id)
    events = [from_stored(s) for s in stored]
    return fold(events)
