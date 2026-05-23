"""Validate a `Wire` against the Plan's bound Assets and their ports.

This is a structural / relational validator, NOT an instance of the
schema-validated-values pattern (no JSON Schema involved). The
checks live here:

  - both endpoint asset_ids are in the Plan's `asset_ids` set
  - both endpoint port_names exist on their referenced Asset.ports
  - source port has `direction=OUTPUT`, target port has
    `direction=INPUT`
  - source and target ports have matching `signal_type` (exact)
  - the wire is not the trivial self-loop (same asset + same port)

The fan-in check (target port already wired by another Wire) is NOT
performed here because it requires the Plan's CURRENT `wires` set —
it lives in the `add_plan_wire` decider directly. Same for duplicate
detection (re-add of an already-present Wire). Those are
collection-membership checks; this module is point-validation of one
proposed Wire against the cross-aggregate context.

Per the locked design at [[project_plan_wiring_design]]:

  - Strict forward-reference: reject if either endpoint port doesn't
    exist on the bound Asset RIGHT NOW. Operators must add ports
    BEFORE wiring against them; remove wires BEFORE removing the
    referenced ports (PostgreSQL FK shape).

The validators read `Asset.ports` and `Plan.asset_ids` only — they
take no I/O dependencies. The handler pre-loads the bound Assets
into a `PlanWireContext` (slice-local, mirrors `PlanBindingContext`
+ `RunStartContext`) before calling the decider.
"""

from collections.abc import Mapping
from uuid import UUID

from cora.equipment.aggregates.asset import Asset, AssetPort, PortDirection
from cora.recipe.aggregates.plan.state import (
    PlanWireAssetNotBoundError,
    PlanWireDirectionMismatchError,
    PlanWirePortNotFoundError,
    PlanWireSelfLoopError,
    PlanWireSignalTypeMismatchError,
    Wire,
)


def _find_port(asset: Asset, port_name: str) -> AssetPort | None:
    """Return the AssetPort with the given name, or None if absent."""
    for port in asset.ports:
        if port.name == port_name:
            return port
    return None


def validate_wire_endpoints(
    wire: Wire,
    *,
    bound_asset_ids: frozenset[UUID],
    assets_by_id: Mapping[UUID, Asset],
) -> None:
    """Validate a Wire's endpoint structure against bound Assets.

    Performs (in order, fail-fast):
      1. self-loop guard (same asset + same port name) → `PlanWireSelfLoopError`
      2. asset-binding check (both endpoint asset_ids in `bound_asset_ids`)
         → `PlanWireAssetNotBoundError`
      3. port-existence check (both port names found on respective
         Asset.ports) → `PlanWirePortNotFoundError`
      4. direction check (source=OUTPUT, target=INPUT)
         → `PlanWireDirectionMismatchError`
      5. signal_type compatibility (exact match)
         → `PlanWireSignalTypeMismatchError`

    `assets_by_id` must contain entries for every bound asset_id the
    wire references; the handler is responsible for providing this
    via `PlanWireContext`. Self-loops on different ports of the same
    Asset ARE allowed (PandABox LUT block self-feedback pattern); the
    self-loop guard rejects ONLY the degenerate case where source and
    target are the same port.
    """
    # 1. self-loop on same port (degenerate)
    if (
        wire.source_asset_id == wire.target_asset_id
        and wire.source_port_name == wire.target_port_name
    ):
        raise PlanWireSelfLoopError(wire)

    # 2. asset-binding check (both endpoints must be bound by the Plan)
    missing_assets = sorted(
        (
            asset_id
            for asset_id in (wire.source_asset_id, wire.target_asset_id)
            if asset_id not in bound_asset_ids
        ),
        key=str,
    )
    if missing_assets:
        # de-dup if both endpoints reference the same missing asset
        unique_missing: list[UUID] = []
        for asset_id in missing_assets:
            if asset_id not in unique_missing:
                unique_missing.append(asset_id)
        raise PlanWireAssetNotBoundError(wire, unique_missing)

    # 3. port-existence check (each endpoint port must exist on its Asset)
    source_asset = assets_by_id[wire.source_asset_id]
    target_asset = assets_by_id[wire.target_asset_id]
    source_port = _find_port(source_asset, wire.source_port_name)
    target_port = _find_port(target_asset, wire.target_port_name)
    missing_ports: list[tuple[UUID, str, str]] = []
    if source_port is None:
        missing_ports.append((wire.source_asset_id, wire.source_port_name, "source"))
    if target_port is None:
        missing_ports.append((wire.target_asset_id, wire.target_port_name, "target"))
    if missing_ports:
        raise PlanWirePortNotFoundError(wire, missing_ports)

    # type narrowing for the remaining checks (mypy/pyright)
    assert source_port is not None
    assert target_port is not None

    # 4. direction check (source must be OUTPUT, target must be INPUT)
    if (
        source_port.direction is not PortDirection.OUTPUT
        or target_port.direction is not PortDirection.INPUT
    ):
        raise PlanWireDirectionMismatchError(
            wire,
            actual_source_direction=source_port.direction.value,
            actual_target_direction=target_port.direction.value,
        )

    # 5. signal_type compatibility (exact match)
    if source_port.signal_type != target_port.signal_type:
        raise PlanWireSignalTypeMismatchError(
            wire,
            source_signal_type=source_port.signal_type,
            target_signal_type=target_port.signal_type,
        )


__all__ = ["validate_wire_endpoints"]
