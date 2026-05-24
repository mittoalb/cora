"""Cross-aggregate context the `update_asset_settings` decider validates against.

`AssetSettingsContext` is built by the `update_asset_settings`
handler from `load_family` calls before reaching the pure decider.
The decider treats the loaded Family entities as opaque domain data
and validates the merged settings against the union of their
declared `settings_schema`s without performing any I/O.

Pattern: same shape as `PlanWireContext` (6h) and
`PlanDefaultParametersContext` (6g-b). Slice-local module by design;
promote to a shared form only after the rule of three.

`families` is the sequence of Family instances declared by the
Asset's `family_ids` field at update time. May be empty when the
Asset has no Family bindings; the strict validator interprets the
empty case plus non-empty settings as a rejection ("no
settings_schema declared"), per the 5g-c "no contract therefore
reject" anchor.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from cora.equipment.aggregates.family.state import Family


@dataclass(frozen=True)
class AssetSettingsContext:
    """Snapshot of upstream Family state at settings validation time."""

    families: Sequence[Family]
