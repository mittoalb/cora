"""Evolver: replay events to reconstruct Fixture state.

Single-event aggregate per Visit-instance pattern: one stream per
fixture_id, exactly one `FixtureRegistered` event per stream. The
evolver therefore only handles the genesis case.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.equipment.aggregates.fixture.events import (
    FixtureEvent,
    FixtureRegistered,
)
from cora.equipment.aggregates.fixture.state import (
    Fixture,
    FixtureAlreadyExistsError,
)


def evolve(
    state: Fixture | None,
    event: FixtureEvent,
) -> Fixture:
    """Apply one event to the current state.

    Genesis-only: the Visit-instance pattern guarantees exactly one
    `FixtureRegistered` event per stream. If a duplicate ever lands
    (replay bug, malformed migration), raise rather than silently
    overwrite the prior state.
    """
    match event:
        case FixtureRegistered(
            fixture_id=fixture_id,
            assembly_id=assembly_id,
            assembly_content_hash=assembly_content_hash,
            surface_id=surface_id,
            slot_asset_bindings=slot_asset_bindings,
            parameter_overrides=parameter_overrides,
            occurred_at=occurred_at,
        ):
            if state is not None:
                raise FixtureAlreadyExistsError(state.id)
            return Fixture(
                id=fixture_id,
                assembly_id=assembly_id,
                assembly_content_hash=assembly_content_hash,
                surface_id=surface_id,
                slot_asset_bindings=slot_asset_bindings,
                parameter_overrides=parameter_overrides,
                registered_at=occurred_at,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[FixtureEvent]) -> Fixture | None:
    """Replay a stream of events from the empty initial state."""
    state: Fixture | None = None
    for event in events:
        state = evolve(state, event)
    return state
