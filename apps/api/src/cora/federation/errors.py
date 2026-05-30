"""BC-application-layer errors for the Federation BC.

These errors are raised by application handlers (not domain logic)
and mapped to HTTP / MCP responses by the BC's exception handlers in
`cora/federation/routes.py`.

Domain errors (raised by aggregates / deciders) live with their
aggregate, for example `aggregates/permit/state.py`,
`aggregates/credential/state.py`, `aggregates/seal/state.py`.

`FederationError` is the BC-level base class; every Federation
application-layer error inherits from it so routes.py can attach a
single catch-all handler when needed. `UnauthorizedError` is the
Authorize-port denial; distinct from each other BC's
`UnauthorizedError` so a Federation 403 is distinguishable from
other BCs' 403s in logs / aggregator filters (documented in
CONTRIBUTING.md "BC-application-layer errors").
"""


class FederationError(Exception):
    """Base class for Federation BC application-layer errors."""


class UnauthorizedError(FederationError):
    """The Authorize port denied the command."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason
