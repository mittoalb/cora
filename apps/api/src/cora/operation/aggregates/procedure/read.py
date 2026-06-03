"""Read repository for the Procedure aggregate.

`load_procedure(event_store, procedure_id) -> Procedure | None`
mirrors `load_supply` / `load_family` / `load_subject`. Used by
the `get_procedure` query slice (10c-a) and update-style command
handlers (10c-b transition slices).

`load_procedure_with_events(event_store, procedure_id)` returns
`tuple[Procedure | None, list[StoredEvent]]`; extends the load shape
for handlers that need both the folded state
AND access to the raw `StoredEvent` payloads (the `conduct_procedure`
handler reads the `RecipeExpansionRecorded` provenance event payload
directly per [[project-run-procedure-replay-design]]). Single
underlying `event_store.load` call; `load_procedure` becomes a thin
wrapper that discards the StoredEvent list to preserve every existing
call site untouched.
"""

from uuid import UUID

from cora.infrastructure.ports import EventStore
from cora.infrastructure.ports.event_store import StoredEvent
from cora.operation.aggregates.procedure.events import from_stored
from cora.operation.aggregates.procedure.evolver import fold
from cora.operation.aggregates.procedure.state import Procedure

_STREAM_TYPE = "Procedure"


async def load_procedure_with_events(
    event_store: EventStore,
    procedure_id: UUID,
) -> tuple[Procedure | None, list[StoredEvent]]:
    """Load Procedure state AND return the raw StoredEvent list.

    Single `event_store.load` call. Returns the folded `Procedure | None`
    AND the raw `list[StoredEvent]` so handlers needing payload-direct
    access (per [[project-run-procedure-replay-design]] §Operation BC
    seam additions) do not double-IO. Most callers want
    `load_procedure` instead; this entry point exists for the recipe
    replay path that scans for `RecipeExpansionRecorded.payload`.
    """
    stored, _version = await event_store.load(_STREAM_TYPE, procedure_id)
    events = [from_stored(s) for s in stored]
    return fold(events), list(stored)


async def load_procedure(event_store: EventStore, procedure_id: UUID) -> Procedure | None:
    """Load and fold a Procedure's event stream into current state.

    Thin wrapper over `load_procedure_with_events` that discards the
    raw StoredEvent list. Existing call sites stay untouched.
    """
    state, _events = await load_procedure_with_events(event_store, procedure_id)
    return state
