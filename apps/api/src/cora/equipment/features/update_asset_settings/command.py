"""The `UpdateAssetSettings` command — intent dataclass for this slice.

`asset_id` is the target Asset aggregate. `settings_patch` is a
dict applied to current settings via RFC 7396 (JSON Merge Patch)
semantics: keys with non-null values are set/replaced; keys with
null are deleted; absent keys are preserved. The principal-id of
the invoker is supplied separately by the application handler.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class UpdateAssetSettings:
    """Update an Asset's settings dict with RFC 7396 merge semantics.

    Validation runs at the handler boundary against the union of the
    Asset's currently-assigned Capabilities' settings_schemas. The
    decider receives the prior state, the merged-result, and the
    Capability schemas to decide whether to emit AssetSettingsUpdated.
    """

    asset_id: UUID
    settings_patch: dict[str, Any]
