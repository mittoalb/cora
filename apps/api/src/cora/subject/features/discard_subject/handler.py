"""Application handler for the `discard_subject` slice.

Built on the actor-stamping `make_subject_actor_update_handler`
factory variant: the envelope's `principal_id` threads into the
decider under `discarded_by`, landing on `SubjectDiscarded.discarded_by`
per [[project_fold_symmetry_design]].
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.subject._subject_update_handler import make_subject_actor_update_handler
from cora.subject.features.discard_subject.command import DiscardSubject
from cora.subject.features.discard_subject.decider import decide


class Handler(Protocol):
    """Callable interface every discard_subject handler implements."""

    async def __call__(
        self,
        command: DiscardSubject,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a discard_subject handler closed over the shared deps."""
    return make_subject_actor_update_handler(
        deps,
        command_name="DiscardSubject",
        log_prefix="discard_subject",
        decide_fn=decide,
        actor_kwarg="discarded_by",
    )
