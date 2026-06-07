"""Application handler for the `measure_subject` slice.

Built on the actor-stamping `make_subject_actor_update_handler`
factory variant: the envelope's `principal_id` threads into the
decider under `measured_by`, landing on `SubjectMeasured.measured_by`
per [[project_fold_symmetry_design]].

Not idempotency-wrapped: update-style commands are inherently
domain-idempotent (second call hits `SubjectCannotMeasureError`).
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.subject._subject_update_handler import make_subject_actor_update_handler
from cora.subject.features.measure_subject.command import MeasureSubject
from cora.subject.features.measure_subject.decider import decide


class Handler(Protocol):
    """Callable interface every measure_subject handler implements."""

    async def __call__(
        self,
        command: MeasureSubject,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a measure_subject handler closed over the shared deps."""
    return make_subject_actor_update_handler(
        deps,
        command_name="MeasureSubject",
        log_prefix="measure_subject",
        decide_fn=decide,
        actor_kwarg="measured_by",
    )
