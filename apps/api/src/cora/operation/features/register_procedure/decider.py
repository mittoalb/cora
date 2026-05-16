"""Pure decider for the `RegisterProcedure` command.

Pure function: given the current Procedure state (None for a fresh
stream) and a `RegisterProcedure` command, returns the events to
append. No I/O, no awaits, no side effects.

`now` and `new_id` are injected by the application handler from the
Clock and IdGenerator ports (the non-determinism principle: capture,
don't recompute).

## Validation

  - State must be None (genesis-only) -> `ProcedureAlreadyExistsError`
  - `kind` is bare `str`; validated 1-50 chars via the shared
    `validate_bounded_text` helper -> `InvalidProcedureKindError`.
    Per the Supply.kind iter-1 lock precedent, kind is NOT a VO; the
    validator is invoked here at the decider, not in `__post_init__`.
  - `name` is wrapped via `ProcedureName(...)` which validates
    1-200 chars in `__post_init__` -> `InvalidProcedureNameError`.

`target_asset_ids` and `parent_run_id` are NOT validated for
existence here per the eventual-consistency stance (precedent: Trust
Conduit zone refs from 3b, Asset parent refs from 5b, Method's
capabilities_needed from 6a). Existence + Decommissioned-lifecycle
gating happens at start_procedure time in 10c-b via
`ProcedureStartContext` (mirrors `RunStartContext` from Run 6f-1).

Initial status is implicit `Defined` (event type IS the state-
change indicator; the genesis evolver hardcodes the mapping). Per
universal industrial + cloud-native consensus, registration produces
a "configured but not running" state.
"""

from datetime import datetime
from uuid import UUID

from cora.infrastructure.bounded_text import validate_bounded_text
from cora.operation.aggregates.procedure import (
    PROCEDURE_KIND_MAX_LENGTH,
    InvalidProcedureKindError,
    Procedure,
    ProcedureAlreadyExistsError,
    ProcedureName,
    ProcedureRegistered,
)
from cora.operation.features.register_procedure.command import RegisterProcedure


def decide(
    state: Procedure | None,
    command: RegisterProcedure,
    *,
    now: datetime,
    new_id: UUID,
) -> list[ProcedureRegistered]:
    """Decide the events produced by registering a new procedure."""
    if state is not None:
        raise ProcedureAlreadyExistsError(state.id)

    # validate + trim kind (bare str; not a VO per Supply.kind precedent)
    kind = validate_bounded_text(
        command.kind,
        max_length=PROCEDURE_KIND_MAX_LENGTH,
        error_class=InvalidProcedureKindError,
    )
    # validate + trim name via VO
    name = ProcedureName(command.name)

    return [
        ProcedureRegistered(
            procedure_id=new_id,
            name=name.value,
            kind=kind,
            target_asset_ids=list(command.target_asset_ids),
            parent_run_id=command.parent_run_id,
            occurred_at=now,
        )
    ]
