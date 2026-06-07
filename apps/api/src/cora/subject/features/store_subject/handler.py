"""Application handler for the `store_subject` slice.

Built on the actor-stamping `make_subject_actor_update_handler`
factory variant: the envelope's `principal_id` threads into the
decider under `stored_by`, landing on `SubjectStored.stored_by`
per [[project_fold_symmetry_design]].
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.subject._subject_update_handler import make_subject_actor_update_handler
from cora.subject.features.store_subject.command import StoreSubject
from cora.subject.features.store_subject.decider import decide


class Handler(Protocol):
    """Callable interface every store_subject handler implements."""

    async def __call__(
        self,
        command: StoreSubject,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a store_subject handler closed over the shared deps."""
    return make_subject_actor_update_handler(
        deps,
        command_name="StoreSubject",
        log_prefix="store_subject",
        decide_fn=decide,
        actor_kwarg="stored_by",
    )
