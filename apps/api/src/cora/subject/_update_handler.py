"""Subject BC's update-handler factory (thin wrapper).

Closes over Subject-specific knobs (stream type, codec, BC-local
`UnauthorizedError`, target-id attribute) and delegates to the
cross-BC `cora.infrastructure.update_handler.make_update_handler`.

Cross-BC hoist landed once Recipe and Run shipped a combined 11
byte-identical longhand handlers; the trigger documented at this
file's earlier longhand body had fired. Slice call sites
(`make_subject_update_handler(...)`) are unchanged across the hoist.

## Subject-side knobs closed over

  - `stream_type = "Subject"`.
  - `target_id_attr = "subject_id"` — every Subject update
    command exposes `subject_id: UUID`. If a future Subject
    command needs a differently-named target field, the slice
    cannot use this factory and must stay longhand.
  - `unauthorized_error = UnauthorizedError` from the Subject BC.
  - The four codec functions imported from
    `cora.subject.aggregates.subject`.

Per-slice inputs (`command_name`, `log_prefix`, `decide_fn`, plus
the optional `extra_log_fields` extractor) pass straight through
to `make_update_handler`. Subject's existing slices (Mount /
Measure / Remove / Return / Store / Discard / Dismount) carry
only `subject_id` in their log lines, so none of them currently
pass `extra_log_fields`.
"""

from collections.abc import Callable, Sequence
from typing import Any

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.update_handler import make_update_handler
from cora.subject.aggregates.subject import (
    SubjectEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.subject.errors import UnauthorizedError


def make_subject_update_handler(
    deps: Kernel,
    *,
    command_name: str,
    log_prefix: str,
    decide_fn: Callable[..., Sequence[SubjectEvent]],
    extra_log_fields: Callable[[Any], dict[str, Any]] | None = None,
):
    """Build an update-style handler for one Subject slice."""
    return make_update_handler(
        deps,
        stream_type="Subject",
        target_id_attr="subject_id",
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


__all__ = ["make_subject_update_handler"]
