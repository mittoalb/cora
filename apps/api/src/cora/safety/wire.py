"""Compose the Safety BC's handlers from `Kernel`.

`wire_safety(deps)` is invoked once from the FastAPI lifespan and the
returned `SafetyHandlers` bundle is stored on `app.state.safety`.
Routes and MCP tools pull their handler out of that bundle. New slices
add a new field on `SafetyHandlers` and a single line in this factory.

Cross-cutting decorators applied here mirror Access / Trust / Subject
/ Equipment / Supply / Operation:

  1. `bind(deps)` -- bare handler.
  2. `with_idempotency` (create-style commands only).
  3. `with_tracing` -- OTel span around every handler call.

## Wired handlers

11a-a:
  - `register_clearance`            (create-style; idempotency-wrapped)
  - `get_clearance`                 (query)

11a-b:
  - `submit_clearance`              (transition; uses make_clearance_update_handler)
  - `begin_review_clearance`        (transition)
  - `record_review_step_clearance`  (transition)
  - `approve_clearance`             (transition)
  - `reject_clearance`              (transition)
  - `activate_clearance`            (transition)

All six 11a-b transition handlers go through `make_clearance_update_handler`
(factory hoisted in 11a-b at the rule-of-three trigger).
"""

from dataclasses import dataclass
from uuid import UUID

from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.observability import with_tracing
from cora.safety.features import (
    activate_clearance,
    approve_clearance,
    begin_review_clearance,
    get_clearance,
    list_clearances,
    record_review_step_clearance,
    register_clearance,
    reject_clearance,
    submit_clearance,
)

_BC = "safety"


@dataclass(frozen=True)
class SafetyHandlers:
    """The Safety BC's handler bundle, each closed over Kernel."""

    register_clearance: register_clearance.IdempotentHandler
    get_clearance: get_clearance.Handler
    list_clearances: list_clearances.Handler
    submit_clearance: submit_clearance.Handler
    begin_review_clearance: begin_review_clearance.Handler
    record_review_step_clearance: record_review_step_clearance.Handler
    approve_clearance: approve_clearance.Handler
    reject_clearance: reject_clearance.Handler
    activate_clearance: activate_clearance.Handler


def wire_safety(deps: Kernel) -> SafetyHandlers:
    """Build the Safety BC handlers from shared dependencies."""
    return SafetyHandlers(
        register_clearance=with_tracing(
            with_idempotency(
                register_clearance.bind(deps),
                deps.idempotency_store,
                command_name="RegisterClearance",
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="RegisterClearance",
            bc=_BC,
        ),
        get_clearance=with_tracing(
            get_clearance.bind(deps),
            command_name="GetClearance",
            bc=_BC,
            kind="query",
        ),
        list_clearances=with_tracing(
            list_clearances.bind(deps),
            command_name="ListClearances",
            bc=_BC,
            kind="query",
        ),
        submit_clearance=with_tracing(
            submit_clearance.bind(deps),
            command_name="SubmitClearance",
            bc=_BC,
        ),
        begin_review_clearance=with_tracing(
            begin_review_clearance.bind(deps),
            command_name="BeginReviewClearance",
            bc=_BC,
        ),
        record_review_step_clearance=with_tracing(
            record_review_step_clearance.bind(deps),
            command_name="RecordReviewStepClearance",
            bc=_BC,
        ),
        approve_clearance=with_tracing(
            approve_clearance.bind(deps),
            command_name="ApproveClearance",
            bc=_BC,
        ),
        reject_clearance=with_tracing(
            reject_clearance.bind(deps),
            command_name="RejectClearance",
            bc=_BC,
        ),
        activate_clearance=with_tracing(
            activate_clearance.bind(deps),
            command_name="ActivateClearance",
            bc=_BC,
        ),
    )
