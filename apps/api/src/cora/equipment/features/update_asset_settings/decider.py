"""Pure decider for the `UpdateAssetSettings` command.

Phase 5g-c. The decider:
  - Raises AssetNotFoundError on empty state
  - Merges the patch into prior settings via RFC 7396 semantics
  - Validates the merged result against the union of the supplied
    Capabilities' settings_schemas (raises InvalidAssetSettingsError
    on validation failure)
  - No-ops (returns []) if the merged result equals the current
    settings (matches 5g-a / 5g-b precedent: identical re-submission
    carries no audit value)
  - Otherwise emits AssetSettingsUpdated(asset_id, settings,
    occurred_at) with the FULL post-merge dict in the payload (NOT
    the patch — readers reconstruct current state without folding
    back through prior events).

The handler is responsible for loading the Capability streams and
passing them into `decide` as the `capabilities` argument; the
decider stays pure (no I/O).
"""

from collections.abc import Sequence
from datetime import datetime

from cora.equipment.aggregates.asset import (
    Asset,
    AssetNotFoundError,
    AssetSettingsUpdated,
)
from cora.equipment.aggregates.asset.settings_validation import (
    validate_settings_against_capabilities,
)
from cora.equipment.aggregates.capability.state import Capability
from cora.equipment.features.update_asset_settings.command import UpdateAssetSettings
from cora.infrastructure.json_merge_patch import merge_patch


def decide(
    state: Asset | None,
    command: UpdateAssetSettings,
    *,
    capabilities: Sequence[Capability],
    now: datetime,
) -> list[AssetSettingsUpdated]:
    """Decide the events produced by an Asset.settings update."""
    if state is None:
        raise AssetNotFoundError(command.asset_id)

    merged = merge_patch(state.settings, command.settings_patch)

    validate_settings_against_capabilities(merged, capabilities)

    if merged == state.settings:
        return []

    return [
        AssetSettingsUpdated(
            asset_id=state.id,
            settings=merged,
            occurred_at=now,
        )
    ]
