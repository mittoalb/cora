"""The `InstallAsset` command - intent dataclass.

Install an Asset specimen into a Mount slot. The Asset must already
exist in CORA (the install_asset handler verifies via the
asset_lookup projection precondition); the Mount must be Active and
its slot must be vacant (no implicit eviction per the design
anti-hook).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class InstallAsset:
    """Install an Asset into a Mount."""

    mount_id: UUID
    asset_id: UUID
