"""Compose the Federation BC's handlers from `Kernel`.

`wire_federation(deps)` is invoked once from the FastAPI lifespan
and the returned `FederationHandlers` bundle is stored on
`app.state.federation`. Routes and MCP tools pull their handler out
of that bundle. New slices add a new field on `FederationHandlers`
and a single line in this factory.

Cross-cutting decorators applied here (when slices land):

  1. `bind(deps)`: bare handler.
  2. `with_idempotency` (create-style commands only): Idempotency-Key
     support. Wrapped before tracing so cache-hits and cache-misses
     both attribute to the tracing span.
  3. `with_tracing`: OTel span around every handler call.

Stage 2a returns an empty bundle: Permit / Credential / Seal slices
land in Stage 2b/2c.
"""

from dataclasses import dataclass

from cora.infrastructure.kernel import Kernel

_BC = "federation"


@dataclass(frozen=True)
class FederationHandlers:
    """The Federation BC's handler bundle, each closed over Kernel.

    Empty in Stage 2a; slices land in Stage 2b/2c.
    """


def wire_federation(deps: Kernel) -> FederationHandlers:
    """Build the Federation BC handlers from shared dependencies."""
    _ = deps
    _ = _BC
    return FederationHandlers()


__all__ = ["FederationHandlers", "wire_federation"]
