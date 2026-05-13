"""Shared scaffolding for the Subject BC's update-style handlers.

Six byte-identical update-style handlers shipped across Phases 4b-d
(mount / measure / remove / return / store / discard). Each followed
the same load + authorize + fold + decide + append template,
differing only in two strings (command_name, log_prefix) and the
imported `decide` function. This module factors the template into
one `make_subject_update_handler(...)` factory so each slice's
handler.py shrinks from ~120 lines to ~50 (a per-slice `Handler`
Protocol plus a 7-line `bind` that supplies the two strings and
the decider).

## What this factory closes over (BC-wide constants)

  - `_STREAM_TYPE = "Subject"` — the event-store stream type for
    every Subject update.
  - `_CONDUIT_DEFAULT_ID = UUID(int=0)` — the conduit_id kwarg
    passed to `deps.authorize` (nil-UUID sentinel; Subject doesn't
    yet know its real conduit_id at handler-call time, so all
    handlers pass the nil sentinel; a future surface-level change
    will plumb HTTP/MCP-specific conduit_ids in).
  - The aggregate event codec (`from_stored`, `to_payload`,
    `event_type_name`, `fold`) imported from
    `cora.subject.aggregates.subject`.
  - `UnauthorizedError` — Subject BC's local error class. Per-BC by
    design (so log search distinguishes which BC denied a command);
    that's why the cross-BC abstraction lives in `cora/infrastructure/`
    only when the BC-specific items can be cleanly threaded through.

## Per-slice inputs

  - `command_name: str` — the canonical PascalCase command name
    (e.g., "MountSubject"). Used in log lines and as the
    NewEvent metadata `command` field.
  - `log_prefix: str` — slice name used as the log-line prefix
    (e.g., "mount_subject" -> "mount_subject.start" /
    `.denied` / `.success`).
  - `decide_fn: Callable[[Subject | None, command, *, datetime],
    Sequence[SubjectEvent]]` — the slice's pure decider. Typed as
    `Callable[..., Sequence[SubjectEvent]]` here because the
    command type varies per slice; pyright sees the precise shape
    at the call site through each slice's `Handler` Protocol.

## Convention: every Subject command exposes `subject_id: UUID`

Captured by the `_SubjectTargetingCommand` Protocol below. The
factory reads the target id directly off the command via this
attribute, and every existing Subject slice command (Mount /
Measure / Remove / Return / Store / Discard) satisfies the
Protocol structurally. If a future Subject command needs a
differently-named target field, the Protocol bound is the place
to widen.

## Why Subject-only (not cross-BC)

Access has only one update-style handler today (`deactivate_actor`).
The BC-specific bits (UnauthorizedError class, log field key
"actor_id" vs "subject_id", aggregate codec) cost more to thread
through a cross-BC factory than they save with a single Access
instance. If Access ever grows a 2nd update-style handler it should
get its own per-BC helper; at the third cross-BC instance we'd
hoist into `cora/infrastructure/` (mirrors the 3b-cleanup precedent
for `to_new_event`).

## Why not a per-handler decorator stack

A `@subject_update_handler(command_name=..., ...)` decorator on a
bare `decide`-like function was considered. The factory shape wins
because:

  - The handler's IO and logging structure is what's shared, not
    pure decision logic — decorating `decide` would still leave
    every slice writing the IO loop.
  - Each slice already has a `decide` exported separately
    (consumed by unit tests); coupling the decorator to it would
    force an awkward bind-time vs decorate-time split.
"""

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.subject.aggregates.subject import (
    Subject,
    SubjectEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.subject.errors import UnauthorizedError

if TYPE_CHECKING:
    from datetime import datetime

_STREAM_TYPE = "Subject"
_CONDUIT_DEFAULT_ID = UUID(int=0)


class _SubjectTargetingCommand(Protocol):
    """Structural contract every Subject update-style command satisfies.

    Declared as a read-only property so frozen-dataclass commands
    satisfy the Protocol (a plain `subject_id: UUID` attribute would
    require write access, which `@dataclass(frozen=True)` doesn't
    provide and pyright flags).
    """

    @property
    def subject_id(self) -> UUID: ...


class _SubjectUpdateHandler(Protocol):
    """The factory's return shape — matches each slice's `Handler` Protocol
    structurally (each slice's Handler is narrower in `command` type, which
    is contravariant, so this widely-typed callable assigns to it).
    """

    async def __call__(
        self,
        command: _SubjectTargetingCommand,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def make_subject_update_handler(
    deps: Kernel,
    *,
    command_name: str,
    log_prefix: str,
    decide_fn: Callable[..., Sequence[SubjectEvent]],
) -> _SubjectUpdateHandler:
    """Build an update-style handler for one Subject slice.

    The returned async callable matches each slice's `Handler`
    Protocol structurally (same shape:
    `(command, *, principal_id, correlation_id, causation_id=None) -> None`).
    """
    log = get_logger(log_prefix)

    async def handler(
        command: _SubjectTargetingCommand,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None:
        subject_id = command.subject_id
        log.info(
            f"{log_prefix}.start",
            command_name=command_name,
            subject_id=str(subject_id),
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
                subject_id=str(subject_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now: datetime = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=subject_id,
        )
        history: list[SubjectEvent] = [from_stored(s) for s in stored]
        state: Subject | None = fold(history)

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
            stream_id=subject_id,
            expected_version=current_version,
            events=new_events,
        )

        log.info(
            f"{log_prefix}.success",
            command_name=command_name,
            subject_id=str(subject_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
