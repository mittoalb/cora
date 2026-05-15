"""Run aggregate's update-handler factory (thin wrapper).

Closes over Run-specific knobs (stream type, codec, BC-local
`UnauthorizedError`, target-id attribute) and delegates to the
cross-BC `cora.infrastructure.update_handler.make_update_handler`.

Cross-BC hoist landed post-7e once Recipe and Run shipped a
combined 11 byte-identical longhand handlers.

## Run-side knobs closed over

  - `stream_type = "Run"`.
  - `target_id_attr = "run_id"` — every Run transition command
    exposes `run_id: UUID` (Hold / Resume / Complete / Abort /
    Stop / Truncate).
  - `unauthorized_error = UnauthorizedError` from the Run BC.
  - The four codec functions imported from
    `cora.run.aggregates.run`.

The terminal slices (Abort / Stop / Truncate) carry `reason: str`
alongside `run_id`. That field IS captured on the emitted event
payload but is intentionally NOT logged at the handler boundary
(matches Subject's discard precedent and Asset's condition
precedent), so none of the Run slices currently pass
`extra_log_fields`.
"""

from collections.abc import Callable, Sequence
from typing import Any

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.update_handler import make_update_handler
from cora.run.aggregates.run import (
    RunEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.run.errors import UnauthorizedError


def make_run_update_handler(
    deps: Kernel,
    *,
    command_name: str,
    log_prefix: str,
    decide_fn: Callable[..., Sequence[RunEvent]],
    extra_log_fields: Callable[[Any], dict[str, Any]] | None = None,
):
    """Build an update-style handler for one Run slice."""
    return make_update_handler(
        deps,
        stream_type="Run",
        target_id_attr="run_id",
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


__all__ = ["make_run_update_handler"]
