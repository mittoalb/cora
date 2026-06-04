"""Context snapshot loaded by the uninstall_asset handler.

The handler folds the Mount stream to get `installed_asset_id`, then
(if non-None) loads the installed Asset's event stream via the bare
`load_asset` repository loader to peek at `Asset.fixture_id`. The
peek result is packaged into this context and consumed by the pure
decider, which raises `MountHasFixtureBoundAssetError` when the
Asset is still bound to a Fixture.

No projection lookup: the Asset's own event stream is the canonical
source of truth for `fixture_id`, set/cleared by
`attach_asset_to_fixture` / `detach_asset_from_fixture` on the Asset
stream. Same shape as `register_fixture` reading per-Asset state via
`load_asset` rather than a projection (the conformance projection
mentioned in the alignment plan ships in a later slice).

`installed_asset_fixture_id` is None when:
  - the slot is vacant (`Mount.installed_asset_id is None`; the
    decider raises `MountIsEmptyError` before consulting this field)
  - the installed Asset has no Fixture back-reference
  - defensively, the installed Asset's stream cannot be folded
    (legacy data integrity gap; uninstall is allowed)
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class UninstallAssetContext:
    """The installed Asset's fixture_id back-reference, or None."""

    installed_asset_fixture_id: UUID | None
