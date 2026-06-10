"""Application handler for the `bind_asset_to_facility` slice.

Update-style handler (loads Asset stream + cross-BC FacilityLookup
result, then calls the pure decider). Mirrors the Slice 8A
`register_asset` handler-vs-decider split: LOAD lives in the
handler, REJECTION lives in the decider, THREADING crosses the
boundary via a typed `FacilityLookupResult | None` argument.

Order of operations:

  1. Authz check via `deps.authz.authorize` (Deny -> UnauthorizedError).
  2. Load Asset stream via `event_store.load` (captures
     `current_version` for the append). `load_asset` would discard
     the version; we need it for the expected_version guard.
  3. Resolve `command.facility_code` via the cross-BC
     `FacilityLookup.lookup_by_code` port. Mirrors the Slice 8A
     register_asset handler precedent.
  4. Call the pure decider with state + command + facility_lookup_result.
  5. Append the emitted `AssetFacilityCodeAssigned` event to the
     Asset stream at `expected_version=current_version`.

Update-style (NOT idempotency-wrapped): retries are domain-
idempotent via `AssetFacilityCodeAlreadyAssignedError` on the
second call.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.asset import (
    AssetEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.bind_asset_to_facility.command import BindAssetToFacility
from cora.equipment.features.bind_asset_to_facility.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId

_STREAM_TYPE = "Asset"
_COMMAND_NAME = "BindAssetToFacility"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every bind_asset_to_facility handler implements."""

    async def __call__(
        self,
        command: BindAssetToFacility,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a bind_asset_to_facility handler closed over the shared deps."""

    async def handler(
        command: BindAssetToFacility,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "bind_asset_to_facility.start",
            command_name=_COMMAND_NAME,
            asset_id=str(command.asset_id),
            facility_code=command.facility_code,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "bind_asset_to_facility.denied",
                command_name=_COMMAND_NAME,
                asset_id=str(command.asset_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.asset_id,
        )
        history: list[AssetEvent] = [from_stored(s) for s in stored]
        asset_state = fold(history)

        facility_lookup_result = await deps.facility_lookup.lookup_by_code(
            FacilityCode(command.facility_code)
        )
        # facility_lookup_result is None -> decider raises
        # AssetFacilityNotFoundError (HTTP 404). The handler only
        # loads the lookup row; the decider owns the rejection.

        domain_events = decide(
            state=asset_state,
            command=command,
            now=now,
            assigned_by=ActorId(principal_id),
            facility_lookup_result=facility_lookup_result,
        )

        new_events = [
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=event.occurred_at,
                event_id=deps.id_generator.new_id(),
                command_name=_COMMAND_NAME,
                correlation_id=correlation_id,
                causation_id=causation_id,
                principal_id=principal_id,
            )
            for event in domain_events
        ]
        await deps.event_store.append(
            stream_type=_STREAM_TYPE,
            stream_id=command.asset_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "bind_asset_to_facility.success",
            command_name=_COMMAND_NAME,
            asset_id=str(command.asset_id),
            facility_code=command.facility_code,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
