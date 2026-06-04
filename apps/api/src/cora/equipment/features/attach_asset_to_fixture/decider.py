"""Pure decider for the `AttachAssetToFixture` command.

Pure function: given the current Asset state, the loaded Asset +
Fixture context, and the command, returns the events to append. No
I/O, no awaits, no side effects.

`now` is injected by the application handler from the Clock port.
"""

from datetime import datetime
from typing import assert_never

from cora.equipment.aggregates.asset import (
    Asset,
    AssetAlreadyAttachedToFixtureError,
    AssetAttachedToFixture,
    AssetCannotAttachToFixtureError,
    AssetLifecycle,
    AssetNotBoundInFixtureError,
    AssetNotFoundError,
)
from cora.equipment.aggregates.fixture import FixtureNotFoundError
from cora.equipment.features.attach_asset_to_fixture.command import AttachAssetToFixture
from cora.equipment.features.attach_asset_to_fixture.context import (
    AttachAssetToFixtureContext,
)


def decide(
    state: Asset | None,
    command: AttachAssetToFixture,
    *,
    context: AttachAssetToFixtureContext,
    now: datetime,
) -> list[AssetAttachedToFixture]:
    """Decide the events produced by attaching an Asset to a Fixture.

    Invariants:
      - context.asset_state must not be None -> AssetNotFoundError
        carrying the target asset_id.
      - context.fixture_state must not be None -> FixtureNotFoundError
        carrying the target fixture_id.
      - asset.fixture_id must currently be None
        -> AssetAlreadyAttachedToFixtureError carrying the current
        fixture_id (no double-attach; detach first via
        detach_asset_from_fixture).
      - asset.lifecycle must not be Decommissioned
        -> AssetCannotAttachToFixtureError carrying the current
        lifecycle.
      - Some binding in fixture.slot_asset_bindings must carry this
        asset_id -> AssetNotBoundInFixtureError (prevents phantom
        back-references; the Fixture was registered with a specific
        binding set and only Assets in that set can be attached).
    """
    _ = state  # we read the Asset via context.asset_state, not the bare state.
    asset = context.asset_state
    if asset is None:
        raise AssetNotFoundError(command.asset_id)

    fixture = context.fixture_state
    if fixture is None:
        raise FixtureNotFoundError(command.fixture_id)

    if asset.fixture_id is not None:
        raise AssetAlreadyAttachedToFixtureError(asset.id, asset.fixture_id)

    # Closed-enum exhaustiveness: if a 5th lifecycle ever lands, the
    # `assert_never` arm raises at type-check time. Mirrors the
    # SlotCardinality match in register_fixture's decider.
    match asset.lifecycle:
        case AssetLifecycle.COMMISSIONED | AssetLifecycle.ACTIVE | AssetLifecycle.MAINTENANCE:
            pass
        case AssetLifecycle.DECOMMISSIONED:
            raise AssetCannotAttachToFixtureError(asset.id, asset.lifecycle)
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(asset.lifecycle)

    bound_asset_ids = {binding.asset_id for binding in fixture.slot_asset_bindings}
    if asset.id not in bound_asset_ids:
        raise AssetNotBoundInFixtureError(asset.id, fixture.id)

    return [
        AssetAttachedToFixture(
            asset_id=asset.id,
            fixture_id=fixture.id,
            occurred_at=now,
        )
    ]
