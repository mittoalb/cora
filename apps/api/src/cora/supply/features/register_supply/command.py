"""The `RegisterSupply` command — intent dataclass for this slice.

Carries the caller-controlled fields: the supply's hierarchical
`scope` (Facility / Sector / Beamline), free-form `kind`
discriminator, operator-readable `name`, and the cross-deployment
convergent `facility_code` (Session 5 Slice 7) binding the supply
to its owning Facility. Server-side concerns (new aggregate id,
wall-clock timestamp, correlation id, per-event ids) are injected
by the handler from infrastructure ports, matching the cross-BC
create-style command shape locked in Access / Trust / Subject /
Equipment.

`scope` is typed as `SupplyScope` (the StrEnum) so callers cannot
pass an invalid value; the route's Pydantic body and the MCP tool's
argument schema both enforce this at the API boundary.

`kind` is bare `str` (free-form, 1-50 chars after trim) per the
[[project_supply_design]] iter-1 lock — closed StrEnum was rejected
universally across the three research corpora; promotion to
`SupplyKind: StrEnum` is a deferred-with-trigger watch item.

`facility_code` is bare `str` on the command (matches the
Permit / Credential / Seal Slice 6E wire convention of bare-str
slugs on commands + typed `FacilityCode` VO on aggregate state).
Route + tool Pydantic regex enforces the `[a-z0-9-]{1,32}` codepoint
contract at the API boundary; the handler wraps in `FacilityCode(...)`
at the port edge before calling `FacilityLookup.lookup_by_code`.

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
    facility_code: str
