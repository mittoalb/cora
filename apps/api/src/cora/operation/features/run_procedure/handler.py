"""Application handler for the `run_procedure` slice.

Thin orchestrator that delegates to `Conductor.conduct()`. The
handler's job is the application-layer concerns the Conductor
itself does not own: command-level authorization (the per-step
`append_procedure_steps` calls already authz internally, but the
RunProcedure entry point gates the entire invocation), envelope
threading, and result conversion from `ConductorResult` to the
slice's `RunProcedureResult` contract.

## Why no `_decider`

Unlike CQRS slices that compute events from state, `run_procedure`
records no new events on the Procedure stream directly: the wrapped
`start_procedure` / `append_procedure_steps` / `complete_procedure` /
`abort_procedure` handlers are the things that write. The slice is
an orchestration entry point, NOT an aggregate-state-mutating
decider. Therefore no `decider.py`, no `context.py`.

## Authorization scope

`RunProcedure` is authz-checked as a distinct command. The wrapped
handlers (start / append / complete / abort) each authz internally
with their OWN command names; an operator authorized to call
`RunProcedure` is NOT automatically authorized for each of those
individually. That's correct: `RunProcedure` is the
operator-friendly entry; the underlying per-FSM-transition
authorization is what the policy engine actually evaluates at
each call site.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation.conductor import Conductor
from cora.operation.errors import UnauthorizedError
from cora.operation.features.run_procedure.command import (
    RunProcedure,
    RunProcedureResult,
)

_COMMAND_NAME = "RunProcedure"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every run_procedure handler implements."""

    async def __call__(
        self,
        command: RunProcedure,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> RunProcedureResult: ...


def bind(deps: Kernel, *, conductor: Conductor) -> Handler:
    """Build a run_procedure handler closed over deps + the Conductor.

    `conductor` is BC-internal: wire_operation constructs it from
    the bound FSM handlers + ControlPort + Kernel infra ports.
    Not promoted to the Kernel since it is Operation-BC-local.
    """

    async def handler(
        command: RunProcedure,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> RunProcedureResult:
        _log.info(
            "run_procedure.start",
            command_name=_COMMAND_NAME,
            procedure_id=str(command.procedure_id),
            step_count=len(command.steps),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
        )

        authz = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(authz, Deny):
            _log.info(
                "run_procedure.denied",
                command_name=_COMMAND_NAME,
                procedure_id=str(command.procedure_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=authz.reason,
            )
            raise UnauthorizedError(authz.reason)

        result = await conductor.conduct(
            procedure_id=command.procedure_id,
            principal_id=principal_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            surface_id=surface_id,
            steps=command.steps,
        )

        _log.info(
            "run_procedure.success",
            command_name=_COMMAND_NAME,
            procedure_id=str(command.procedure_id),
            completed_count=result.completed_count,
            succeeded=result.succeeded,
            failure_class=(result.failure.error_class if result.failure is not None else None),
        )

        return RunProcedureResult(
            procedure_id=result.procedure_id,
            completed_count=result.completed_count,
            succeeded=result.succeeded,
            failure=result.failure,
        )

    return handler
