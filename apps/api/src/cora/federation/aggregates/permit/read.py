# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# (asyncpg's typed-Pool/Connection narrows poorly in strict mode; matches
# the convention in cora/calibration/aggregates/calibration/read.py for the
# same reason.)

"""Read repository for the Permit aggregate.

`load_permit(event_store, permit_id) -> Permit | None` mirrors
`load_clearance` / `load_calibration`. Used by the `get_permit`
query slice and update-style command handlers that pre-load state
before the decider.

`PermitLifecycleTimestamps` + `load_permit_timestamps` mirror the
Calibration Path C precedent
(`project_template_aggregate_timestamps`): lifecycle bookkeeping
timestamps live on the projection populated from each event's
envelope `occurred_at`, not on the aggregate state. Stage 2 lands
the `proj_permit_summary` projection table and replaces the stub
with the real query.

`is_active` / `is_revoked` / `is_outbound` / `is_inbound` are pure
projection helpers usable without the event store.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg

from cora.federation.aggregates.permit.events import from_stored
from cora.federation.aggregates.permit.evolver import fold
from cora.federation.aggregates.permit.state import (
    InboundTerms,
    OutboundTerms,
    Permit,
    PermitStatus,
)
from cora.infrastructure.ports import EventStore

_STREAM_TYPE = "Permit"


@dataclass(frozen=True, slots=True)
class PermitLifecycleTimestamps:
    """Observed wall-clock timestamps for Permit lifecycle events.

    Sourced from `proj_permit_summary`, not from aggregate state.
    `defined_at` is set once on `PermitDefined` (the envelope
    `occurred_at` of the genesis event); `activated_at`,
    `suspended_at`, `resumed_at`, and `revoked_at` are set or
    overwritten by the matching transition events. Optional fields
    stay `None` until their event fires.
    """

    defined_at: datetime
    activated_at: datetime | None
    suspended_at: datetime | None
    resumed_at: datetime | None
    revoked_at: datetime | None


def is_active(state: Permit) -> bool:
    return state.status is PermitStatus.ACTIVE


def is_revoked(state: Permit) -> bool:
    return state.status is PermitStatus.REVOKED


def is_outbound(state: Permit) -> bool:
    return isinstance(state.terms, OutboundTerms)


def is_inbound(state: Permit) -> bool:
    return isinstance(state.terms, InboundTerms)


async def load_permit(event_store: EventStore, permit_id: UUID) -> Permit | None:
    stored, _version = await event_store.load(_STREAM_TYPE, permit_id)
    events = [from_stored(s) for s in stored]
    return fold(events)


async def load_permit_timestamps(
    pool: asyncpg.Pool,
    permit_id: UUID,
) -> PermitLifecycleTimestamps | None:
    """Read the lifecycle-timestamp tuple from the projection.

    Stage 2 lands `proj_permit_summary` and the real fetch; this Stage 1
    stub returns `None` so update-style handlers can compose against
    the eventual surface without yet depending on a projection table
    that does not exist.
    """
    _ = pool
    _ = permit_id
    return None
