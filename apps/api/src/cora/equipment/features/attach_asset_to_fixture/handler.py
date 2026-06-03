"""Application handler for the `attach_asset_to_fixture` slice.

Longhand update-style handler (cannot use the per-aggregate factory
because it loads a CROSS-aggregate Fixture reference BEFORE calling
the decider):

  1. Authz check (Deny -> UnauthorizedError).
  2. Load target Asset stream via `event_store.load` (need
     `current_version` for the append; load_asset discards it) AND
     target Fixture state via `load_fixture` concurrently via
     `asyncio.create_task` + ordered awaits. A single `asyncio.gather`
     across both would widen the result type to a union; the
     create-task-then-await pair keeps each return narrowed.
  3. Call pure decider with context + command + now.
  4. Append the emitted event to the Asset stream
     (single-stream-write, expected_version=current_version).

The Fixture stream is NOT mutated by this slice; the projection-side
conformance check uses the new Asset.fixture_id back-reference plus
the Fixture's snapshot of slot_asset_bindings to answer "does this
Fixture have all its Assets attached?" queries.

Update-style (not idempotency-wrapped): retries are domain-idempotent
via AssetAlreadyAttachedToFixtureError on the second call.
"""

import asyncio
from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.asset import (
    AssetEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.equipment.aggregates.fixture import load_fixture
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.attach_asset_to_fixture.command import AttachAssetToFixture
from cora.equipment.features.attach_asset_to_fixture.context import (
    AttachAssetToFixtureContext,
)
from cora.equipment.features.attach_asset_to_fixture.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_STREAM_TYPE = "Asset"
_COMMAND_NAME = "AttachAssetToFixture"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every attach_asset_to_fixture handler implements."""

    async def __call__(
        self,
        command: AttachAssetToFixture,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an attach_asset_to_fixture handler closed over the shared deps."""

    async def handler(
        command: AttachAssetToFixture,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "attach_asset_to_fixture.start",
            command_name=_COMMAND_NAME,
            asset_id=str(command.asset_id),
            fixture_id=str(command.fixture_id),
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
                "attach_asset_to_fixture.denied",
                command_name=_COMMAND_NAME,
                asset_id=str(command.asset_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        # Single event_store.load for the Asset stream (captures
        # expected_version for the append below); concurrent Fixture
        # load via load_fixture. Two awaits via gather so the round
        # trip latency is the slower of the two, not the sum.
        asset_load_task = asyncio.create_task(
            deps.event_store.load(
                stream_type=_STREAM_TYPE,
                stream_id=command.asset_id,
            )
        )
        fixture_state = await load_fixture(deps.event_store, command.fixture_id)
        stored, current_version = await asset_load_task
        history: list[AssetEvent] = [from_stored(s) for s in stored]
        asset_state = fold(history)

        context = AttachAssetToFixtureContext(
            asset_state=asset_state,
            fixture_state=fixture_state,
        )

        domain_events = decide(
            state=asset_state,
            command=command,
            context=context,
            now=now,
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
            "attach_asset_to_fixture.success",
            command_name=_COMMAND_NAME,
            asset_id=str(command.asset_id),
            fixture_id=str(command.fixture_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
