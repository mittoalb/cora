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

Phase 4a ships only `register_subject`. Future fields (mount, measure,
remove, dispose, get) land per slice in 4b-4e.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.infrastructure.deps import SharedDeps
from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.observability import with_tracing
from cora.subject.features import register_subject

_BC = "subject"


@dataclass(frozen=True)
class SubjectHandlers:
    """The Subject BC's handler bundle, each closed over SharedDeps."""

    register_subject: register_subject.IdempotentHandler


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
    )
