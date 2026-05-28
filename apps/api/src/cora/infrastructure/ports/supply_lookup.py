"""SupplyLookup port: cross-BC query for Supply BC's status projection.

Used by Run BC's `start_run` handler and Operation BC's
`start_procedure` handler to gate Run / Procedure start on the
presence of at least one AVAILABLE Supply for every kind that the
governing Method declared in its `needed_supplies` field.

## Convention

Third cross-BC port (after `Authorize` and `ClearanceLookup`,
mirrored by `CautionLookup`): one implementor (Supply BC ships
`PostgresSupplyLookup` reading `proj_supply_summary`), multiple
consumers (Run today; Operation alongside). Lives in
`cora.infrastructure.ports` per the existing pattern. Shaped around
the consumer's need (the start-time gate needs "which Supplies of
each requested kind are registered, and in what status?"); the
adapter translates Supply BC's projection columns to this shape.

## Available-only semantics

The decider, not this port, gates on `status == SupplyStatus.AVAILABLE`.
The port returns every matching Supply regardless of status so the
decider can produce a useful diagnostic ("LiquidNitrogen has a
Supply but it's Unavailable") distinct from absence ("no LN2 Supply
registered at all"). Decommissioned rows are filtered at the query
layer per [[project_deregister_supply_design]] (tombstones should
not count toward gate satisfaction). See
[[project_supply_preflight_gate_design]] for the shared decision.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class SupplyReference:
    """Summary row from `proj_supply_summary` for the pre-flight gate.

    Carries the minimal columns the start-time decider needs to
    decide pass/fail and to produce a diagnostic. Loaded by the
    handler via `SupplyLookup.find_supplies_by_kind` and handed to
    the decider as values in `needed_supplies_satisfaction`.

    `status` is the StrEnum value as a plain string (matches the
    projection's `TEXT` column); the decider treats it opaquely and
    partitions on `"Available"`.

    `supply_id` is typed `UUID` for cross-port symmetry with
    `ClearanceReference.clearance_id` and `CautionReference.caution_id`.
    """

    supply_id: UUID
    kind: str
    scope: str
    name: str
    status: str


class SupplyLookup(Protocol):
    """Cross-BC port: query Supply's status projection from Run + Operation BCs."""

    async def find_supplies_by_kind(
        self,
        *,
        kinds: frozenset[str],
    ) -> Mapping[str, list[SupplyReference]]:
        """Return Supplies grouped by kind for every requested kind.

        The returned mapping is keyed by kind string and contains
        ONLY the kinds for which at least one non-Decommissioned
        Supply is registered. Kinds with no registered Supply are
        absent from the mapping (the decider treats absence as a
        missing-kind rejection distinct from a no-Available
        rejection).

        Decommissioned Supplies are filtered out at the query layer:
        tombstones do not count toward satisfaction. Operators who
        deregister a typo-Supply do not see that row contributing to
        a satisfied gate.

        Empty input (`kinds = frozenset()`) returns an empty
        mapping; the handler should short-circuit before calling the
        port for Methods with no `needed_supplies`.
        """
        ...


class AllSatisfiedSupplyLookup:
    """Test-default stub: returns ONE synthetic Available Supply per requested kind.

    Mirrors `AlwaysCoveredClearanceLookup`'s role for `ClearanceLookup`:
    tests that don't care about the Supply gate get this stub from
    `build_postgres_deps` defaults, so existing Run / Procedure tests
    don't have to seed real Supplies. Tests that exercise the gate
    explicitly override with the real adapter (`PostgresSupplyLookup`)
    and seed Supplies via `register_supply` + `mark_supply_available`.

    The synthetic Supply has `status="Available"` so every kind
    requested by Method.needed_supplies satisfies the decider's
    gate. Tests that need to assert the missing-kind or no-Available
    rejection paths MUST use the real `PostgresSupplyLookup`
    adapter, not this stub.
    """

    async def find_supplies_by_kind(
        self,
        *,
        kinds: frozenset[str],
    ) -> Mapping[str, list[SupplyReference]]:
        from cora.infrastructure.routing import NIL_SENTINEL_ID

        return {
            kind: [
                SupplyReference(
                    supply_id=NIL_SENTINEL_ID,
                    kind=kind,
                    scope="Facility",
                    name=f"<test stub: {kind}>",
                    status="Available",
                )
            ]
            for kind in kinds
        }


class NoSuppliesRegisteredLookup:
    """Test stub: returns an empty mapping for any input.

    Use when a test needs to exercise the missing-kind rejection
    path without seeding any real Supplies (decider raises
    `RunRequiresAvailableSupplyError` or
    `ProcedureRequiresAvailableSupplyError` for every kind in
    `Method.needed_supplies`).
    """

    async def find_supplies_by_kind(
        self,
        *,
        kinds: frozenset[str],
    ) -> Mapping[str, list[SupplyReference]]:
        _ = kinds
        return {}
