"""Procedure aggregate's update-handler factory (thin wrapper).

Closes over Procedure-specific knobs (stream type, codec, BC-local
`UnauthorizedError`, target-id attribute) and delegates to the
cross-BC `cora.infrastructure.update_handler.make_update_handler`.

## Hoist trigger

The first wave shipped two update-style handlers (complete_procedure +
abort_procedure) longhand-via-direct-make_update_handler call, with a
docstring note pointing at the rule-of-three trigger. Adding
`truncate_procedure` as the third update slice fired the trigger.
This factory hoists the shared scaffolding so each slice's handler.py
shrinks from ~70 lines to a 7-line `bind` that supplies a name + a
log-prefix + the decider. Mirrors `_supply_update_handler` (Supply
hoisted after 5 transitions) and `cora.run._update_handler` (Run
hoisted at 11 byte-identical instances cross-BC).

## Per-aggregate, not per-BC

Operation is a single-aggregate BC today; the factory still scopes to
the Procedure aggregate (not the BC) so a future Operation-sibling
aggregate would get its own factory rather than parameterizing this
one. Same per-aggregate scoping rationale as `_supply_update_handler`.

## Procedure-side knobs closed over

  - `stream_type = "Procedure"`.
  - `target_id_attr = "procedure_id"` -- every Procedure transition
    command exposes `procedure_id: UUID` (CompleteProcedure /
    AbortProcedure / TruncateProcedure).
  - `unauthorized_error = UnauthorizedError` from the Operation BC.
  - The four codec functions imported from
    `cora.operation.aggregates.procedure`.

The terminal slices (Abort / Truncate) carry `reason: str` alongside
`procedure_id`. That field IS captured on the emitted event payload
but is intentionally NOT logged at the handler boundary (matches
Run BC's terminal-slice precedent), so the Procedure slices currently
do not pass `extra_log_fields`. TruncateProcedure also carries
`interrupted_at: datetime | None`; same posture (captured on the
event payload, not on the handler log line).

NOTE: `start_procedure` is NOT routed through this factory because
it pre-loads cross-aggregate context (each target Asset) and builds a
`ProcedureStartContext` for the decider. The cross-BC factory loads
exactly one event-store stream; multi-stream slices stay longhand.
"""

from collections.abc import Callable, Sequence
from typing import Any

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.update_handler import make_update_handler
from cora.operation.aggregates.procedure import (
    ProcedureEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.operation.errors import UnauthorizedError


def make_procedure_update_handler(
    deps: Kernel,
    *,
    command_name: str,
    log_prefix: str,
    decide_fn: Callable[..., Sequence[ProcedureEvent]],
    extra_log_fields: Callable[[Any], dict[str, Any]] | None = None,
):
    """Build an update-style handler for one Procedure transition slice."""
    return make_update_handler(
        deps,
        stream_type="Procedure",
        target_id_attr="procedure_id",
        from_stored=from_stored,
        to_payload=to_payload,
        event_type_name=event_type_name,
        fold=fold,
        unauthorized_error=UnauthorizedError,
        command_name=command_name,
        log_prefix=log_prefix,
        decide_fn=decide_fn,
        extra_log_fields=extra_log_fields,
    )


__all__ = ["make_procedure_update_handler"]
