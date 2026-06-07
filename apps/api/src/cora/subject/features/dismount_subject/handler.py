"""Application handler for the `dismount_subject` slice.

Built on the actor-stamping `make_subject_actor_update_handler`
factory variant: the envelope's `principal_id` threads into the
decider under `dismounted_by`, landing on
`SubjectDismounted.dismounted_by` per
[[project_fold_symmetry_design]].

Not idempotency-wrapped: dismount is strict-not-idempotent at the
decider (second call hits SubjectCannotDismountError because the
Subject is now in Received status).
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.subject._subject_update_handler import make_subject_actor_update_handler
from cora.subject.features.dismount_subject.command import DismountSubject
from cora.subject.features.dismount_subject.decider import decide


class Handler(Protocol):
    """Callable interface every dismount_subject handler implements."""

    async def __call__(
        self,
        command: DismountSubject,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a dismount_subject handler closed over the shared deps."""
    return make_subject_actor_update_handler(
        deps,
        command_name="DismountSubject",
        log_prefix="dismount_subject",
        decide_fn=decide,
        actor_kwarg="dismounted_by",
    )
