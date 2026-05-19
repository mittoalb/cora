"""Application handler for the `append_procedure_step` slice.

Lazy open-on-first-write + batch append. Two-step non-transactional
write mirroring 6f-5b's `append_run_reading` precedent (which mirrors
8c-b's `append_reasoning_entry`):

  1. Load Procedure via `load_procedure` (fold-on-read).
  2. Reject if Procedure is NOT in Running (steps require Running:
     Defined hasn't started, terminals have ended) ->
     ProcedureStepsLogbookClosedError.
  3. If `procedure.steps_logbook_id` is None: emit
     `ProcedureStepsLogbookOpened` to the Procedure stream.
  4. Read the logbook_id (from existing or just-emitted).
  5. Construct `ProcedureStep` rows with the logbook_id +
     correlation_id + procedure_id from the envelope.
  6. `step_store.append(rows)`, silent dedup via Postgres PK (or
     InMemory dict setdefault).

## Self-healing on failure

  - Step 3 fails (concurrency on Procedure stream): handler retries
    from step 1; the conflicting writer either also opened a steps
    logbook (we now see it open on reload, skip step 3) OR registered
    a different event entirely (re-validate Running status, then
    proceed).
  - Step 6 fails after step 3 succeeded: dangling open logbook with
    no entries. The next call sees the logbook is open, skips step 3,
    and retries the entry append. UUIDv7 PK + at-most-one-open
    invariant make this fully recoverable.

## Why not idempotency-wrapped

Natural idempotence: the at-most-one-open-logbook invariant catches
double-opens; entry-store PK catches double-appends. Wrapping the
slice in `with_idempotency` would add no value beyond what the
domain already guarantees. Same reasoning as
`append_run_reading` (6f-5b).

## Defensive `step_kind` validation

Pydantic at the API layer catches invalid values via `Literal[...]`
on the request body. The handler ALSO validates against
`STEP_KIND_VALUES` so direct in-process callers (sagas, tests) get
the same protection. Same defensive-validation posture as the
sampling_procedure check in `append_run_reading`.
"""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.ports.event_store import ConcurrencyError
from cora.operation.aggregates.procedure import (
    LOGBOOK_KIND_STEPS,
    STEP_KIND_VALUES,
    STEPS_LOGBOOK_SCHEMA,
    InvalidStepKindError,
    ProcedureNotFoundError,
    ProcedureStatus,
    ProcedureStep,
    ProcedureStepsLogbookClosedError,
    ProcedureStepsLogbookOpened,
    StepStore,
    event_type_name,
    load_procedure,
    to_payload,
)
from cora.operation.errors import UnauthorizedError
from cora.operation.features.append_procedure_step.command import (
    AppendProcedureSteps,
    ProcedureStepInput,
)

_STREAM_TYPE = "Procedure"
_COMMAND_NAME = "AppendProcedureStep"
_CONDUIT_DEFAULT_ID = UUID(int=0)
_LAZY_OPEN_MAX_RETRIES = 3
"""Bounded retry count for the lazy-open ConcurrencyError loop.

Each retry re-loads the Procedure (so subsequent attempts see any
concurrently-opened logbook + skip the open step). 3 attempts covers
the realistic burst-write window; beyond that we surface the conflict
as ConcurrencyError. Mirrors 6f-5b's bound."""

_OPEN_STATUSES: frozenset[ProcedureStatus] = frozenset({ProcedureStatus.RUNNING})

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every append_procedure_step handler implements."""

    async def __call__(
        self,
        command: AppendProcedureSteps,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = _CONDUIT_DEFAULT_ID,
    ) -> int: ...


def bind(deps: Kernel, *, step_store: StepStore) -> Handler:
    """Build an append_procedure_step handler closed over deps + store.

    `step_store` is BC-internal (constructed in `wire_operation` from
    `deps.pool` for Postgres, or `InMemoryStepStore` for
    `app_env=test`). Not promoted to Kernel per the per-category-
    writer pattern locked at gate-review L9 (mirrors Run BC's
    ReadingStore and Decision BC's ReasoningStore).
    """

    async def handler(
        command: AppendProcedureSteps,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = _CONDUIT_DEFAULT_ID,
    ) -> int:
        _log.info(
            "append_procedure_step.start",
            command_name=_COMMAND_NAME,
            procedure_id=str(command.procedure_id),
            entry_count=len(command.entries),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
        )

        authz = await deps.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=_CONDUIT_DEFAULT_ID,
            surface_id=surface_id,
        )
        if isinstance(authz, Deny):
            _log.info(
                "append_procedure_step.denied",
                command_name=_COMMAND_NAME,
                procedure_id=str(command.procedure_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=authz.reason,
            )
            raise UnauthorizedError(authz.reason)

        # Defensive per-entry validation. Pydantic catches these at the
        # API boundary; the in-handler check protects direct callers
        # (sagas, tests) and provides a single, consistent error class
        # per failure mode regardless of caller path.
        for entry in command.entries:
            if entry.step_kind not in STEP_KIND_VALUES:
                raise InvalidStepKindError(entry.step_kind, STEP_KIND_VALUES)

        # Resolve the steps logbook id, opening it lazily on the first
        # append. Retries on ConcurrencyError (a parallel writer
        # incrementing the Procedure stream's version between our load +
        # append): the retry re-loads, and either sees the logbook now
        # open (skips the open) or proceeds with a fresh version.
        # Bounded retry, beyond _LAZY_OPEN_MAX_RETRIES the conflict
        # surfaces as ConcurrencyError rather than infinite spin.
        opened_logbook_now = False
        logbook_id: UUID | None = None
        for attempt in range(_LAZY_OPEN_MAX_RETRIES):
            procedure = await load_procedure(deps.event_store, command.procedure_id)
            if procedure is None:
                raise ProcedureNotFoundError(command.procedure_id)

            # Status guard: Running-only. Re-checked on every retry
            # attempt because a concurrent writer could have transitioned
            # the Procedure to terminal between our prior load and this
            # retry.
            if procedure.status not in _OPEN_STATUSES:
                raise ProcedureStepsLogbookClosedError(procedure.id, procedure.status)

            if procedure.steps_logbook_id is not None:
                logbook_id = procedure.steps_logbook_id
                break

            now = deps.clock.now()
            new_logbook_id = deps.id_generator.new_id()
            open_event = ProcedureStepsLogbookOpened(
                procedure_id=command.procedure_id,
                logbook_id=new_logbook_id,
                kind=LOGBOOK_KIND_STEPS,
                schema=STEPS_LOGBOOK_SCHEMA,
                occurred_at=now,
            )
            stored_open = to_new_event(
                event_type=event_type_name(open_event),
                payload=to_payload(open_event),
                occurred_at=open_event.occurred_at,
                event_id=deps.id_generator.new_id(),
                command_name=_COMMAND_NAME,
                correlation_id=correlation_id,
                causation_id=causation_id,
                principal_id=principal_id,
            )
            _, current_version = await deps.event_store.load(
                stream_type=_STREAM_TYPE,
                stream_id=command.procedure_id,
            )
            try:
                await deps.event_store.append(
                    stream_type=_STREAM_TYPE,
                    stream_id=command.procedure_id,
                    expected_version=current_version,
                    events=[stored_open],
                )
            except ConcurrencyError:
                _log.info(
                    "append_procedure_step.lazy_open_concurrency_retry",
                    command_name=_COMMAND_NAME,
                    procedure_id=str(command.procedure_id),
                    attempt=attempt,
                )
                continue
            logbook_id = new_logbook_id
            opened_logbook_now = True
            break
        else:  # pragma: no cover  # retry-exhaustion guard
            raise ConcurrencyError(
                stream_type=_STREAM_TYPE,
                stream_id=command.procedure_id,
                expected=-1,
                actual=-1,
            )

        assert logbook_id is not None  # loop guarantees this on break

        rows = [
            _build_row(
                entry,
                command.procedure_id,
                logbook_id,
                principal_id,
                correlation_id,
                causation_id,
                fallback_now=deps.clock.now(),
            )
            for entry in command.entries
        ]
        await step_store.append(rows)

        _log.info(
            "append_procedure_step.success",
            command_name=_COMMAND_NAME,
            procedure_id=str(command.procedure_id),
            logbook_id=str(logbook_id),
            entry_count=len(rows),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            opened_logbook=opened_logbook_now,
        )
        return len(rows)

    return handler


def _build_row(
    entry: ProcedureStepInput,
    procedure_id: UUID,
    logbook_id: UUID,
    actor_id: UUID,
    correlation_id: UUID,
    causation_id: UUID | None,
    *,
    fallback_now: object,
) -> ProcedureStep:
    """Compose the producer's input plus envelope context into a
    ProcedureStep row ready for the store.

    `occurred_at` defaults to `fallback_now` (deps.clock.now()) when
    the producer omits it. `actor_id` is the principal that submitted
    the command (taken from the envelope, not from the entry, per
    PII-vault posture).
    """
    assert isinstance(fallback_now, datetime)
    occurred_at = entry.occurred_at if entry.occurred_at is not None else fallback_now
    return ProcedureStep(
        event_id=entry.event_id,
        procedure_id=procedure_id,
        logbook_id=logbook_id,
        actor_id=actor_id,
        command_name=_COMMAND_NAME,
        step_kind=entry.step_kind,
        payload=entry.payload,
        sampled_at=entry.sampled_at,
        occurred_at=occurred_at,
        correlation_id=correlation_id,
        causation_id=causation_id,
    )
