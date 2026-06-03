"""Context snapshot loaded by the attach_asset_to_fixture handler.

Single-stream-write + projection-precondition pattern: the handler
loads the target Asset state plus the target Fixture state BEFORE
calling the decider, packs the results into this VO, and hands it
to the pure decider for invariant enforcement.

`asset_state` is `None` when the asset_id does not resolve (decider
raises `AssetNotFoundError`).

`fixture_state` is `None` when the fixture_id does not resolve
(decider raises `FixtureNotFoundError`).
"""

from dataclasses import dataclass

from cora.equipment.aggregates.asset import Asset
from cora.equipment.aggregates.fixture import Fixture


@dataclass(frozen=True)
class AttachAssetToFixtureContext:
    """Snapshot of Asset + Fixture existence checks for attach_asset_to_fixture."""

    asset_state: Asset | None
    fixture_state: Fixture | None
