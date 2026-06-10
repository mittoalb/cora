"""Read repositories for the Role aggregate.

`load_role(event_store, role_id) -> Role | None` mirrors
`load_family` / `load_capability`. 3A ships the EventStore-replay
loader only; a projection-backed `load_role_timestamps` is not
present because Role has no FSM at 3A (single `RoleDefined` event;
no Versioned / Deprecated transitions to denormalize). When the
deferred Lock 14 versioning lands, the lifecycle-timestamps helper
joins this module alongside `load_role`.

`find_missing_role_ids(event_store, ids)` is the Plan-side
existence-check helper consumed by 3D's `bind_plan_role` (handler-side
RoleLookup precondition) and 3E's `update_capability_suggested_roles`.
Cheap when ids resolve; concurrent stream-loads via `asyncio.gather`.

`_STREAM_TYPE = "Role"`. The stream-type string is the event store's
internal categorization key for this aggregate.
"""

import asyncio
from collections.abc import Iterable
from uuid import UUID

from cora.equipment.aggregates.role.events import from_stored
from cora.equipment.aggregates.role.evolver import fold
from cora.equipment.aggregates.role.state import Role
from cora.infrastructure.ports import EventStore

_STREAM_TYPE = "Role"


async def load_role(event_store: EventStore, role_id: UUID) -> Role | None:
    """Load and fold a Role's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, role_id)
    events = [from_stored(s) for s in stored]
    return fold(events)


async def find_missing_role_ids(
    event_store: EventStore,
    role_ids: Iterable[UUID],
) -> frozenset[UUID]:
    """Return the subset of `role_ids` that do NOT resolve to a Role stream.

    Loads each id's stream concurrently via `load_role` +
    `asyncio.gather`. Cheap when the input set is small (the operational
    case for 3B's `add_family_presents_as` decider, 3D's
    `bind_plan_role` handler, and 3E's
    `update_capability_suggested_roles` handler). The empty input
    short-circuits without dispatching any awaits.
    """
    ids_tuple = tuple(role_ids)
    if not ids_tuple:
        return frozenset()
    loaded = await asyncio.gather(*(load_role(event_store, rid) for rid in ids_tuple))
    return frozenset(rid for rid, role in zip(ids_tuple, loaded, strict=True) if role is None)


__all__ = [
    "find_missing_role_ids",
    "load_role",
]
