"""Pure decider for the `RegisterSupply` command.

Pure function: given the current Supply state (None for a fresh
stream) and a `RegisterSupply` command, returns the events to
append. No I/O, no awaits, no side effects.

`now` and `new_id` are injected by the application handler from the
Clock and IdGenerator ports (the non-determinism principle: capture,
don't recompute).

## Validation

  - State must be None (genesis-only) -> `SupplyAlreadyExistsError`
  - `kind` is bare `str`; validated 1-50 chars via the shared
    `validate_bounded_text` helper -> `InvalidSupplyKindError`. Per
    the iter-1 gate-review lock, kind is NOT a VO; the validator is
    invoked here at the decider, not in `__post_init__`.
  - `name` is wrapped via `SupplyName(...)` which validates 1-200
    chars in `__post_init__` -> `InvalidSupplyNameError`.

Initial status is implicit `Unknown` (event type IS the state-
change indicator; the genesis evolver hardcodes the mapping). Per
universal industrial + cloud-native consensus on registration-time
state.
"""

from datetime import datetime
from uuid import UUID

from cora.infrastructure.bounded_text import validate_bounded_text
from cora.supply.aggregates.supply import (
    SUPPLY_KIND_MAX_LENGTH,
    InvalidSupplyKindError,
    Supply,
    SupplyAlreadyExistsError,
    SupplyName,
    SupplyRegistered,
)
from cora.supply.features.register_supply.command import RegisterSupply


def decide(
    state: Supply | None,
    command: RegisterSupply,
    *,
    now: datetime,
    new_id: UUID,
) -> list[SupplyRegistered]:
    """Decide the events produced by registering a new supply."""
    if state is not None:
        raise SupplyAlreadyExistsError(state.id)

    # validate + trim kind (bare str; not a VO per iter-1 lock)
    kind = validate_bounded_text(
        command.kind,
        max_length=SUPPLY_KIND_MAX_LENGTH,
        error_class=InvalidSupplyKindError,
    )
    # validate + trim name via VO
    name = SupplyName(command.name)

    return [
        SupplyRegistered(
            supply_id=new_id,
            scope=command.scope.value,
            kind=kind,
            name=name.value,
            occurred_at=now,
        )
    ]
