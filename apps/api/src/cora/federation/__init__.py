"""Federation BC.

Publish-pull cross-facility federation: governs Permit /
Credential / Seal aggregates per
[[project_federation_port_design]] (Stage 1 lock).

Permit unifies the two sides of a bilateral publish-pull
relationship through a `direction`-tagged terms union: an outbound
Permit authorizes a peer facility to read a scope-bounded subset of
this facility's published artifacts at a stated ABI tier floor; an
inbound Permit authorizes this facility to pull from a named peer
with a matching scope and acceptable canonicalization / receipt
posture. Credential carries the opaque key-material pointer (signing
/ verification / authentication / encryption / seal-online-signing /
seal-offline-root) per facility and audience. Seal is the
per-facility singleton that signs the head pointer over the
published registry tree.

Stage 2a scaffolds BC wiring (errors, routes, tools, wire,
projection / subscriber registration entry points); slices and
projection modules land in Stage 2b/2c.
"""

from cora.federation._projections import register_federation_projections
from cora.federation._subscribers import register_federation_subscribers
from cora.federation.errors import FederationError, UnauthorizedError
from cora.federation.routes import register_federation_routes
from cora.federation.tools import register_federation_tools
from cora.federation.wire import FederationHandlers, wire_federation

__all__ = [
    "FederationError",
    "FederationHandlers",
    "UnauthorizedError",
    "register_federation_projections",
    "register_federation_routes",
    "register_federation_subscribers",
    "register_federation_tools",
    "wire_federation",
]
