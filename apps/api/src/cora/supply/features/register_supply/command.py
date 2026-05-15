"""The `RegisterSupply` command — intent dataclass for this slice.

Carries the caller-controlled fields: the supply's hierarchical
`scope` (Facility / Sector / Beamline), free-form `kind`
discriminator, and operator-readable `name`. Server-side concerns
(new aggregate id, wall-clock timestamp, correlation id, per-event
ids) are injected by the handler from infrastructure ports, matching
the cross-BC create-style command shape locked in Access / Trust /
Subject / Equipment.

`scope` is typed as `SupplyScope` (the StrEnum) so callers cannot
pass an invalid value; the route's Pydantic body and the MCP tool's
argument schema both enforce this at the API boundary.

`kind` is bare `str` (free-form, 1-50 chars after trim) per the
[[project_supply_design]] iter-1 lock — closed StrEnum was rejected
universally across the three research corpora; promotion to
`SupplyKind: StrEnum` is a deferred-with-trigger watch item.

Status is implicit at registration (`Unknown`) per universal
industrial + cloud-native consensus and is NOT part of the command
— see the Supply aggregate's `state.py` docstring for the
enum-in-state, derived-from-event-type-in-evolver convention.
"""

from dataclasses import dataclass

from cora.supply.aggregates.supply import SupplyScope


@dataclass(frozen=True)
class RegisterSupply:
    """Register a new continuously-available resource (lands in `Unknown`)."""

    scope: SupplyScope
    kind: str
    name: str
