"""Shared scaffolding for the Asset aggregate's update-style handlers.

Five update-style Asset transition handlers shipped across Phases
5c-5e (activate / decommission / relocate / enter_maintenance /
restore_from_maintenance). Four are byte-identical scaffolding
around per-slice decide bodies; the fifth (`relocate_asset`) carries
an extra `to_parent_id` diagnostic log field (its command has more
than one operationally relevant id) and stays longhand. Each of the
four matches the same load + authorize + fold + decide + append
template, differing only in two strings (command_name, log_prefix)
and the imported `decide` function. This module factors the template
into one `make_asset_update_handler(...)` factory so each compatible
slice's handler.py shrinks from ~120 lines to ~50 (a per-slice
`Handler` Protocol plus a 7-line `bind` that supplies the two
strings and the decider).

**Per-aggregate, not per-BC.** Equipment owns two aggregates
(Capability + Asset). This factory only handles Asset transitions —
it hardcodes `_STREAM_TYPE = "Asset"` and uses the Asset event
codec. When Capability lifecycle transitions land in 5f+, they get
their own `make_capability_update_handler` factory in a sibling
module rather than parameterizing this one (per-aggregate scoping
keeps each factory honest about what it knows). Subject's
`make_subject_update_handler` looks BC-named only because Subject is
a single-aggregate BC; same per-aggregate scoping applies there.

## What this factory closes over

  - `_STREAM_TYPE = "Asset"` — the event-store stream type.
  - `_CONDUIT_DEFAULT_ID = UUID(int=0)` — the conduit_id kwarg
    passed to `deps.authorize` (nil-UUID sentinel; Equipment doesn't
    yet know its real conduit_id at handler-call time, so all
    handlers pass the nil sentinel; a future surface-level change
    will plumb HTTP/MCP-specific conduit_ids in).
  - The aggregate event codec (`from_stored`, `to_payload`,
    `event_type_name`, `fold`) imported from
    `cora.equipment.aggregates.asset`.
  - `UnauthorizedError` — Equipment BC's local error class. Per-BC
    by design (so log search distinguishes which BC denied a
    command); that's why the cross-BC abstraction lives in
    `cora/infrastructure/` only when the BC-specific items can be
    cleanly threaded through.

## Per-slice inputs

  - `command_name: str` — the canonical PascalCase command name
    (for example "ActivateAsset"). Used in log lines and as the
    NewEvent metadata `command` field.
  - `log_prefix: str` — slice name used as the log-line prefix
    (for example "activate_asset" -> "activate_asset.start" /
    `.denied` / `.success`).
  - `decide_fn: Callable[[Asset | None, command, *, datetime],
    Sequence[AssetEvent]]` — the slice's pure decider. Typed as
    `Callable[..., Sequence[AssetEvent]]` here because the command
    type varies per slice; pyright sees the precise shape at the
    call site through each slice's `Handler` Protocol.

## Convention: every targeted Asset command exposes `asset_id: UUID`

Captured by the `_AssetTargetingCommand` Protocol below. The factory
reads the target id directly off the command via this attribute, and
every existing single-field Asset transition command (Activate /
Decommission / EnterMaintenance / RestoreFromMaintenance) satisfies
the Protocol structurally. RelocateAsset also has `asset_id` but
carries additional fields (`to_parent_id`, `reason`) that we want to
log; it stays longhand for that reason.

## Why Equipment-only (not cross-BC)

Subject already has its own `_update_handler.py` factory (4d-cleanup,
6 instances). Each per-aggregate factory threads its own
`UnauthorizedError`, log field key (`"asset_id"` vs `"subject_id"`),
and aggregate codec. Hoisting cross-BC requires generic-ifying those
three knobs, and the LOC saving is small relative to the type-system
ceremony. Defer to a 3rd cross-BC instance (when Recipe lands its
own update-style handlers); at that point the 3b-cleanup precedent
for `to_new_event` applies.
"""

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from cora.equipment.aggregates.asset import (
    Asset,
    AssetEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.equipment.errors import UnauthorizedError
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny

if TYPE_CHECKING:
    from datetime import datetime

_STREAM_TYPE = "Asset"
_CONDUIT_DEFAULT_ID = UUID(int=0)


class _AssetTargetingCommand(Protocol):
    """Structural contract every single-field Asset transition command satisfies.

    Declared as a read-only property so frozen-dataclass commands
    satisfy the Protocol (a plain `asset_id: UUID` attribute would
    require write access, which `@dataclass(frozen=True)` doesn't
    provide and pyright flags). Same precedent as Subject's
    `_SubjectTargetingCommand`.
    """

    @property
    def asset_id(self) -> UUID: ...


class _AssetUpdateHandler(Protocol):
    """The factory's return shape — matches each slice's `Handler` Protocol
    structurally (each slice's Handler is narrower in `command` type, which
    is contravariant, so this widely-typed callable assigns to it).
    """

    async def __call__(
        self,
        command: _AssetTargetingCommand,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def make_asset_update_handler(
    deps: Kernel,
    *,
    command_name: str,
    log_prefix: str,
    decide_fn: Callable[..., Sequence[AssetEvent]],
) -> _AssetUpdateHandler:
    """Build an update-style handler for one Asset slice.

    The returned async callable matches each slice's `Handler`
    Protocol structurally (same shape:
    `(command, *, principal_id, correlation_id, causation_id=None) -> None`).
    """
    log = get_logger(log_prefix)

    async def handler(
        command: _AssetTargetingCommand,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None:
        asset_id = command.asset_id
        log.info(
            f"{log_prefix}.start",
            command_name=command_name,
            asset_id=str(asset_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
        )

        decision = await deps.authorize(
            principal_id=principal_id,
            command_name=command_name,
            conduit_id=_CONDUIT_DEFAULT_ID,
        )
        if isinstance(decision, Deny):
            log.info(
                f"{log_prefix}.denied",
                command_name=command_name,
                asset_id=str(asset_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now: datetime = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=asset_id,
        )
        history: list[AssetEvent] = [from_stored(s) for s in stored]
        state: Asset | None = fold(history)

        domain_events = decide_fn(state=state, command=command, now=now)

        new_events = [
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=event.occurred_at,
                event_id=deps.id_generator.new_id(),
                command_name=command_name,
                correlation_id=correlation_id,
                causation_id=causation_id,
                principal_id=principal_id,
            )
            for event in domain_events
        ]
        await deps.event_store.append(
            stream_type=_STREAM_TYPE,
            stream_id=asset_id,
            expected_version=current_version,
            events=new_events,
        )

        log.info(
            f"{log_prefix}.success",
            command_name=command_name,
            asset_id=str(asset_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
