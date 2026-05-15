"""Practice's update-handler factory (thin wrapper).

See `cora.recipe._method_update_handler` for the per-aggregate
scoping rationale shared across Recipe's three aggregates.

## Practice-side knobs closed over

  - `stream_type = "Practice"`.
  - `target_id_attr = "practice_id"` — every Practice transition
    command exposes `practice_id: UUID` (DeprecatePractice /
    VersionPractice).
  - `unauthorized_error = UnauthorizedError` from the Recipe BC.
  - The four codec functions imported from
    `cora.recipe.aggregates.practice`.

`version_practice` carries `version_tag: str` alongside
`practice_id` and passes an `extra_log_fields` extractor at bind
time to preserve the pre-hoist log shape.
"""

from collections.abc import Callable, Sequence
from typing import Any

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.update_handler import make_update_handler
from cora.recipe.aggregates.practice import (
    PracticeEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.recipe.errors import UnauthorizedError


def make_practice_update_handler(
    deps: Kernel,
    *,
    command_name: str,
    log_prefix: str,
    decide_fn: Callable[..., Sequence[PracticeEvent]],
    extra_log_fields: Callable[[Any], dict[str, Any]] | None = None,
):
    """Build an update-style handler for one Practice slice."""
    return make_update_handler(
        deps,
        stream_type="Practice",
        target_id_attr="practice_id",
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


__all__ = ["make_practice_update_handler"]
