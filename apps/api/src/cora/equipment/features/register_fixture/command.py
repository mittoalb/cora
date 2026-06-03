"""The `RegisterFixture` command - intent for the register_fixture slice.

Carries the target `assembly_id`, the operator-supplied
`slot_asset_bindings` (frozenset of (slot_name, asset_id) pairs),
the operator-supplied `parameter_overrides` dict (validated against
the Assembly's `parameter_overrides_schema`), and the `surface_id`
for authz scoping.

Server-side concerns (new fixture_id, wall-clock timestamp,
correlation id, per-event ids, assembly_content_hash snapshot) are
injected by the application handler from infrastructure ports or
read off the loaded Assembly state.

Cross-aggregate references checked by the handler before the decider:
  - assembly_id must resolve to a defined Assembly (not Deprecated).
  - Every asset_id in slot_asset_bindings must resolve to a
    registered Asset (handler loads them concurrently).

Cross-aggregate invariants checked by the decider:
  - Slot cardinality is satisfied by the bindings.
  - Each mapped Asset's family_ids intersect the slot's
    required_family_ids (Family-set match).
  - parameter_overrides validates against the Assembly's
    parameter_overrides_schema.
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from cora.equipment.aggregates.fixture import SlotAssetBinding


@dataclass(frozen=True)
class RegisterFixture:
    """Materialize an Assembly blueprint into a Fixture (concrete cluster of Assets)."""

    assembly_id: UUID
    slot_asset_bindings: frozenset[SlotAssetBinding] = field(
        default_factory=frozenset[SlotAssetBinding]
    )
    parameter_overrides: dict[str, Any] = field(default_factory=dict[str, Any])
    surface_id: UUID | None = None
