"""Context snapshot loaded by the register_fixture handler.

Single-stream-write + projection-precondition pattern: the handler
loads the target Assembly state plus every referenced Asset state
BEFORE calling the decider, packs the results into this VO, and
hands it to the pure decider for invariant enforcement.

`assembly_state` is `None` when the assembly_id does not resolve
(decider raises `AssemblyNotFoundError`).

`family_ids_by_asset_id` maps each referenced asset_id to its
`family_ids` set, or `None` when the asset_id did not resolve.
A `None` value tells the decider to raise
`FixtureAssetNotFoundError` carrying the missing id
(sorted-first for deterministic responses).
"""

from dataclasses import dataclass, field
from uuid import UUID

from cora.equipment.aggregates.assembly import Assembly


@dataclass(frozen=True)
class RegisterFixtureContext:
    """Snapshot of Assembly + Asset existence checks for register_fixture."""

    assembly_state: Assembly | None
    family_ids_by_asset_id: dict[UUID, frozenset[UUID] | None] = field(
        default_factory=dict[UUID, frozenset[UUID] | None]
    )
