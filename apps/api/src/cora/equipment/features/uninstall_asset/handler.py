"""Application handler for the `uninstall_asset` slice.

Longhand handler (cannot use `make_mount_update_handler` because it
loads cross-aggregate state BEFORE calling the decider): folds the
Mount stream, then if a specimen is installed, folds the installed
Asset's stream via the bare `load_asset` repository loader to peek
at `Asset.fixture_id`, packages the result into context, and calls
the pure decider with state + context.

The cross-aggregate read uses the Asset event store (NOT a
projection): `Asset.fixture_id` is canonically owned by the Asset
stream and set/cleared by `attach_asset_to_fixture` /
`detach_asset_from_fixture` on that stream. Same shape as
`register_fixture` reading per-Asset state via `load_asset`.

Single-stream-write (Mount stream) + cross-stream-read (Asset
stream) pattern. The same eventual-consistency caveat as the other
longhand handlers applies: the Asset stream read and the Mount
stream append are not in one serializable txn; an attach of this
Asset between read and append could leave the Mount empty with a
live Fixture pointing at the just-uninstalled Asset. Acceptable for
v1 (rare operation, small window, observable inconsistency via the
conformance projection when it ships); promote to SERIALIZABLE or
PG advisory lock at first incident.

Not idempotency-wrapped: update-style commands are inherently
domain-idempotent at the aggregate level (second uninstall hits
`MountIsEmptyError`); apply only when cached-success-on-retry
semantics are needed.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.asset import load_asset
from cora.equipment.aggregates.mount import (
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.uninstall_asset.command import UninstallAsset
from cora.equipment.features.uninstall_asset.context import UninstallAssetContext
from cora.equipment.features.uninstall_asset.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_STREAM_TYPE = "Mount"
_COMMAND_NAME = "UninstallAsset"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every uninstall_asset handler implements."""

    async def __call__(
        self,
        command: UninstallAsset,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an uninstall_asset handler closed over the shared deps."""

    async def handler(
        command: UninstallAsset,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "uninstall_asset.start",
            command_name=_COMMAND_NAME,
            mount_id=str(command.mount_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "uninstall_asset.denied",
                command_name=_COMMAND_NAME,
                mount_id=str(command.mount_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.mount_id,
        )
        history = [from_stored(s) for s in stored]
        state = fold(history)

        # Cross-aggregate read: if a specimen is installed, fold the
        # Asset's own stream to peek at fixture_id. None when slot is
        # vacant (decider raises MountIsEmptyError before consulting
        # context) or when the installed Asset has no Fixture
        # back-reference. Defensive None when the Asset stream cannot
        # be folded (legacy data integrity gap; uninstall is allowed).
        if state is not None and state.installed_asset_id is not None:
            installed_asset = await load_asset(deps.event_store, state.installed_asset_id)
            installed_fixture_id = installed_asset.fixture_id if installed_asset else None
        else:
            installed_fixture_id = None
        context = UninstallAssetContext(installed_asset_fixture_id=installed_fixture_id)

        domain_events = decide(
            state=state,
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
            stream_id=command.mount_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "uninstall_asset.success",
            command_name=_COMMAND_NAME,
            mount_id=str(command.mount_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
