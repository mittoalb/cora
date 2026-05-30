"""Settings-loadable shape for the Operation BC Conductor's per-prefix routing.

The actual `ControlPort` adapter classes live in
`cora.operation.adapters.*` (substrate-specific code) and the
factory that materialises them lives in
`cora.operation.adapters.control_port_factory`. This module ONLY
carries the typed config dataclass the `Settings` field uses, so
infrastructure can validate the env var at startup without
importing any BC-specific adapter.

Mirrors the layering used for `IdentityProviderConfig` (the typed
config + validation lives in infrastructure; the auth-side
factories that consume it live in BC + composition-root code).

## Env var shape

The `Settings.control_port_routes` field reads from
`CONTROL_PORT_ROUTES` as a JSON list of objects. Example for a 2-BM
deployment where most PVs are CA but the area-detector image PVs
ride PVA:

    CONTROL_PORT_ROUTES='[
      {"prefix": "2bma:cam1:image", "substrate": "epics_pva"},
      {"prefix": "2bma:", "substrate": "epics_ca"}
    ]'

Empty / unset = the Operation BC's `wire_operation` uses
`InMemoryControlPort` (legacy + test convenience).
"""

from typing import Literal

from pydantic import BaseModel, Field

Substrate = Literal["in_memory", "epics_ca", "epics_pva"]
"""The closed set of ControlPort substrates a deployment can select.

`in_memory` is the test + opt-out default; `epics_ca` + `epics_pva`
are the production EPICS adapters. New substrates land here as
additive literal values plus a matching arm in the BC-side
`build_control_port` factory's `_build_substrate` switch.
"""


class ControlPortRoute(BaseModel):
    """One adapter binding in the per-prefix `ControlPortRegistry` routing table.

    `prefix` is the address-string prefix the registry uses for
    longest-prefix-match dispatch. `substrate` selects which adapter
    class the factory will construct for this route.
    """

    prefix: str = Field(..., min_length=1)
    substrate: Substrate

    model_config = {"extra": "forbid"}


__all__ = ["ControlPortRoute", "Substrate"]
