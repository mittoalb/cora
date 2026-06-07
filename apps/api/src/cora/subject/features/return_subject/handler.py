"""Application handler for the `return_subject` slice.

Built on the actor-stamping `make_subject_actor_update_handler`
factory variant: the envelope's `principal_id` threads into the
decider under `returned_by`, landing on `SubjectReturned.returned_by`
per [[project_fold_symmetry_design]].
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.subject._subject_update_handler import make_subject_actor_update_handler
from cora.subject.features.return_subject.command import ReturnSubject
from cora.subject.features.return_subject.decider import decide


class Handler(Protocol):
    """Callable interface every return_subject handler implements."""

    async def __call__(
        self,
        command: ReturnSubject,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a return_subject handler closed over the shared deps."""
    return make_subject_actor_update_handler(
        deps,
        command_name="ReturnSubject",
        log_prefix="return_subject",
        decide_fn=decide,
        actor_kwarg="returned_by",
    )
