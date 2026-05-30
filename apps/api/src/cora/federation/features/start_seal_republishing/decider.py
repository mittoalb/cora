"""Pure decider for the `StartSealRepublishing` command.

Single-source transition: `Live -> Republishing`. Strict-not-
idempotent (matches the Credential rotation / Permit transition
precedents): starting republishing against an already Republishing
Seal raises `SealCannotStartRepublishingError`.

`started_by_actor_id` is handler-injected from the request envelope's
`principal_id` per the non-determinism principle (capture, don't
recompute). The decider is pure: state + command + injected
non-determinism in, events out.

## Validation

  - State must not be None (Seal must exist)
    -> SealNotFoundError
  - Current status must be `Live`
    -> SealCannotStartRepublishingError

`reason` on the command is intentionally not threaded into the event:
the locked `SealRepublishingStarted` event payload carries
`(facility_id, started_by_actor_id, occurred_at)` only. The command
field exists so future audit overlays can pick it up without a wire
break.
"""

from datetime import datetime
from uuid import UUID

from cora.federation.aggregates.seal import (
    Seal,
    SealCannotStartRepublishingError,
    SealNotFoundError,
    SealRepublishingStarted,
    SealStatus,
)
from cora.federation.features.start_seal_republishing.command import (
    StartSealRepublishing,
)


def decide(
    state: Seal | None,
    command: StartSealRepublishing,
    *,
    now: datetime,
    started_by_actor_id: UUID,
) -> list[SealRepublishingStarted]:
    """Decide the events produced by starting republishing on a Live Seal.

    Invariants:
      - State must not be None -> SealNotFoundError
      - Current status must be Live -> SealCannotStartRepublishingError
    """
    if state is None:
        raise SealNotFoundError(command.facility_id)
    if state.status is not SealStatus.LIVE:
        raise SealCannotStartRepublishingError(state.facility_id, state.status)

    return [
        SealRepublishingStarted(
            facility_id=state.facility_id,
            started_by_actor_id=started_by_actor_id,
            occurred_at=now,
        )
    ]


__all__ = ["decide"]
