"""Compose the Equipment BC's handlers from `SharedDeps`.

`wire_equipment(deps)` is invoked once from the FastAPI lifespan
and the returned `EquipmentHandlers` bundle is stored on
`app.state.equipment`. Routes and MCP tools pull their handler out
of that bundle. New slices (commands or queries) add a new field
on `EquipmentHandlers` and a single line in this factory.

Cross-cutting decorators applied here mirror Access / Trust /
Subject (composition order matters — innermost first):

1. `bind(deps)` — bare handler.
2. `with_idempotency` (create-style commands only) — Idempotency-Key
   support. Wrapped before tracing so cache-hits and cache-misses
   both attribute to the tracing span.
3. `with_tracing` — OTel span around every handler call. Records
   `cora.bc`, `cora.command` / `cora.query` attributes.

Phase 5a shipped `define_capability` + `get_capability`. Phase 5b
adds `register_asset` (create-style; idempotency-wrapped). Asset
lifecycle transitions land in 5c+. Queries skip idempotency: a
re-read returning the same state is the desired behavior, no
Idempotency-Key needed.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.equipment.features import define_capability, get_capability, register_asset
from cora.infrastructure.deps import SharedDeps
from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.observability import with_tracing

_BC = "equipment"


@dataclass(frozen=True)
class EquipmentHandlers:
    """The Equipment BC's handler bundle, each closed over SharedDeps.

    Phase 5a shipped `define_capability` (create-style; idempotency-
    wrapped) and `get_capability` (read side). Phase 5b adds
    `register_asset` (create-style; idempotency-wrapped). Asset
    lifecycle / hierarchy slices land in 5c-5e; Capability
    transitions in 5f+.
    """

    define_capability: define_capability.IdempotentHandler
    get_capability: get_capability.Handler
    register_asset: register_asset.IdempotentHandler


def wire_equipment(deps: SharedDeps) -> EquipmentHandlers:
    """Build the Equipment BC handlers from shared dependencies."""
    return EquipmentHandlers(
        define_capability=with_tracing(
            with_idempotency(
                define_capability.bind(deps),
                deps.idempotency_store,
                command_name="DefineCapability",
                # Handler returns UUID; cache as str (jsonb-friendly) and
                # rebuild via UUID() on retrieval.
                serialize_result=str,
                deserialize_result=UUID,
            ),
            command_name="DefineCapability",
            bc=_BC,
        ),
        get_capability=with_tracing(
            get_capability.bind(deps),
            command_name="GetCapability",
            bc=_BC,
            kind="query",
        ),
        register_asset=with_tracing(
            with_idempotency(
                register_asset.bind(deps),
                deps.idempotency_store,
                command_name="RegisterAsset",
                serialize_result=str,
                deserialize_result=UUID,
            ),
            command_name="RegisterAsset",
            bc=_BC,
        ),
    )
