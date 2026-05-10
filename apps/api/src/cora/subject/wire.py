"""Compose the Subject BC's handlers from `SharedDeps`.

`wire_subject(deps)` is invoked once from the FastAPI lifespan and
the returned `SubjectHandlers` bundle is stored on `app.state.subject`.
Routes and MCP tools pull their handler out of that bundle. New
slices (commands or queries) add a new field on `SubjectHandlers`
and a single line in this factory.

Cross-cutting decorators applied here mirror Access and Trust
(composition order matters — innermost first):

1. `bind(deps)` — bare handler.
2. `with_idempotency` (create-style commands only) — Idempotency-Key
   support (`cora.infrastructure.idempotency`). Wrapped before
   tracing so cache-hits and cache-misses both attribute to the
   tracing span.
3. `with_tracing` — OTel span around every handler call. Records
   `cora.bc`, `cora.command` / `cora.query` attributes.

Phase 4a shipped `register_subject`. Phase 4b adds `mount_subject`
(first state-transition slice; update-style; not idempotency-wrapped
because update-style commands are inherently domain-idempotent via
`SubjectCannotMountError` on retry — see CONTRIBUTING.md). Remaining
transitions (measure, remove, dispose) land in 4c-4d; the get_subject
query in 4e.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.infrastructure.deps import SharedDeps
from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.observability import with_tracing
from cora.subject.features import mount_subject, register_subject

_BC = "subject"


@dataclass(frozen=True)
class SubjectHandlers:
    """The Subject BC's handler bundle, each closed over SharedDeps.

    Phase 4a shipped `register_subject` (create-style; idempotency-
    wrapped). Phase 4b adds `mount_subject` (update-style; bare
    Handler, no idempotency wrap).
    """

    register_subject: register_subject.IdempotentHandler
    mount_subject: mount_subject.Handler


def wire_subject(deps: SharedDeps) -> SubjectHandlers:
    """Build the Subject BC handlers from shared dependencies."""
    return SubjectHandlers(
        register_subject=with_tracing(
            with_idempotency(
                register_subject.bind(deps),
                deps.idempotency_store,
                command_name="RegisterSubject",
                # Handler returns UUID; cache as str (jsonb-friendly) and
                # rebuild via UUID() on retrieval.
                serialize_result=str,
                deserialize_result=UUID,
            ),
            command_name="RegisterSubject",
            bc=_BC,
        ),
        mount_subject=with_tracing(
            mount_subject.bind(deps),
            command_name="MountSubject",
            bc=_BC,
        ),
    )
