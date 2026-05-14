"""Compose the Subject BC's handlers from `Kernel`.

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

Phase 4a shipped `register_subject`. Phase 4b added `mount_subject`.
Phase 4c added `measure_subject` and `remove_subject`. Phase 4d added
the three terminal disposition handlers (`return_subject` /
`store_subject` / `discard_subject`). Phase 4e adds the read side
(`get_subject`). All transition handlers are bare (no idempotency
wrap) — update-style commands are inherently domain-idempotent via
the corresponding `SubjectCannot<X>Error` on retry (see
CONTRIBUTING.md). Queries skip idempotency: a re-read returning
the same state is the desired behavior, no Idempotency-Key needed.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.observability import with_tracing
from cora.subject.features import (
    discard_subject,
    dismount_subject,
    get_subject,
    list_subjects,
    measure_subject,
    mount_subject,
    register_subject,
    remove_subject,
    return_subject,
    store_subject,
)

_BC = "subject"


@dataclass(frozen=True)
class SubjectHandlers:
    """The Subject BC's handler bundle, each closed over Kernel.

    Phase 4a shipped `register_subject` (create-style; idempotency-
    wrapped). Phases 4b-c added the active-phase transitions
    (`mount_subject`, `measure_subject`, `remove_subject`) — all
    update-style with bare Handler protocols. Phase 4d added the
    three terminal disposition handlers (`return_subject`,
    `store_subject`, `discard_subject`) — all also update-style
    with bare Handler protocols. Phase 4e added the read side
    (`get_subject`).
    """

    register_subject: register_subject.IdempotentHandler
    mount_subject: mount_subject.Handler
    dismount_subject: dismount_subject.Handler
    measure_subject: measure_subject.Handler
    remove_subject: remove_subject.Handler
    return_subject: return_subject.Handler
    store_subject: store_subject.Handler
    discard_subject: discard_subject.Handler
    get_subject: get_subject.Handler
    list_subjects: list_subjects.Handler


def wire_subject(deps: Kernel) -> SubjectHandlers:
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
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="RegisterSubject",
            bc=_BC,
        ),
        mount_subject=with_tracing(
            mount_subject.bind(deps),
            command_name="MountSubject",
            bc=_BC,
        ),
        dismount_subject=with_tracing(
            dismount_subject.bind(deps),
            command_name="DismountSubject",
            bc=_BC,
        ),
        measure_subject=with_tracing(
            measure_subject.bind(deps),
            command_name="MeasureSubject",
            bc=_BC,
        ),
        remove_subject=with_tracing(
            remove_subject.bind(deps),
            command_name="RemoveSubject",
            bc=_BC,
        ),
        return_subject=with_tracing(
            return_subject.bind(deps),
            command_name="ReturnSubject",
            bc=_BC,
        ),
        store_subject=with_tracing(
            store_subject.bind(deps),
            command_name="StoreSubject",
            bc=_BC,
        ),
        discard_subject=with_tracing(
            discard_subject.bind(deps),
            command_name="DiscardSubject",
            bc=_BC,
        ),
        get_subject=with_tracing(
            get_subject.bind(deps),
            command_name="GetSubject",
            bc=_BC,
            kind="query",
        ),
        list_subjects=with_tracing(
            list_subjects.bind(deps),
            command_name="ListSubjects",
            bc=_BC,
            kind="query",
        ),
    )
