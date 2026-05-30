"""The `UninstallAsset` command - intent dataclass.

Uninstall whatever specimen is currently in a Mount's slot. The
command takes the mount_id only (not the asset_id): the slot
knows what's there. The emitted event carries
`asset_id=state.installed_asset_id` for audit.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class UninstallAsset:
    """Uninstall the currently-installed Asset from a Mount."""

    mount_id: UUID
    reason: str
