"""The `AttachAssetToFixture` command - intent for the slice.

Carries the target Asset's `asset_id` and the target `fixture_id`.
The slot_name is NOT carried: it lives on the Fixture's
`slot_asset_bindings` (each binding is a (slot_name, asset_id)
pair). The Asset side only records the back-reference.

Server-side concerns (wall-clock timestamp, correlation id,
per-event id) are injected by the application handler from
infrastructure ports.

Cross-aggregate references checked by the handler before the decider:
  - asset_id must resolve to a registered Asset.
  - fixture_id must resolve to a registered Fixture.

Cross-aggregate invariants checked by the decider:
  - Asset.fixture_id must currently be None (no double-attach;
    detach first via detach_asset_from_fixture).
  - Asset.lifecycle must not be Decommissioned.
  - Some binding in Fixture.slot_asset_bindings must carry this
    asset_id (prevents phantom back-references).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AttachAssetToFixture:
    """Bind an existing Asset to a registered Fixture."""

    asset_id: UUID
    fixture_id: UUID
