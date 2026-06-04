"""Pure decider for the `DetachAssetFromFixture` command.

Pure function: given the current Asset state and the command,
returns the events to append. No I/O, no awaits, no side effects.

`now` is injected by the application handler from the Clock port.

The decider does NOT load or check Fixture state: detach only
clears the Asset's back-reference. The defensive fixture_id check
fires purely against `asset.fixture_id`.

Lifecycle is NOT checked: detach is allowed in any lifecycle
(including Decommissioned) so an operator can clean up the back-
reference on a retired Asset. This is asymmetric with attach (which
rejects Decommissioned to prevent wiring a retired Asset into a new
Fixture), but operationally correct for the cleanup workflow.
"""

from datetime import datetime

from cora.equipment.aggregates.asset import (
    Asset,
    AssetAttachedToDifferentFixtureError,
    AssetDetachedFromFixture,
    AssetNotAttachedToFixtureError,
    AssetNotFoundError,
)
from cora.equipment.features.detach_asset_from_fixture.command import DetachAssetFromFixture


def decide(
    state: Asset | None,
    command: DetachAssetFromFixture,
    *,
    now: datetime,
) -> list[AssetDetachedFromFixture]:
    """Decide the events produced by detaching an Asset from a Fixture.

    Invariants:
      - state must not be None -> AssetNotFoundError carrying the
        target asset_id.
      - asset.fixture_id must currently NOT be None
        -> AssetNotAttachedToFixtureError (strict-not-idempotent:
        a second detach raises).
      - asset.fixture_id must equal the requested fixture_id
        -> AssetAttachedToDifferentFixtureError carrying both the
        requested and current ids (defensive race-condition guard).
    """
    if state is None:
        raise AssetNotFoundError(command.asset_id)

    if state.fixture_id is None:
        raise AssetNotAttachedToFixtureError(state.id)

    if state.fixture_id != command.fixture_id:
        raise AssetAttachedToDifferentFixtureError(
            state.id,
            requested_fixture_id=command.fixture_id,
            current_fixture_id=state.fixture_id,
        )

    return [
        AssetDetachedFromFixture(
            asset_id=state.id,
            fixture_id=state.fixture_id,
            occurred_at=now,
        )
    ]
