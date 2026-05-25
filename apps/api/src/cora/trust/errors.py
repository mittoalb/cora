"""BC-application-layer errors for the Trust BC.

These errors are raised by application handlers (not domain logic) and
mapped to HTTP / MCP responses by the BC's exception handlers in
`cora/trust/routes.py`.

Domain errors (raised by aggregates / deciders) live with their
aggregate, for example `aggregates/zone/state.py`.

Distinct class from `cora.access.errors.UnauthorizedError`: each BC
owns its own application-error namespace so a Trust 403 is
distinguishable from an Access 403 in logs / aggregator filters.
Cross-BC consumers catching authorization failures import per-BC.
"""


class UnauthorizedError(Exception):
    """The Authorize port denied the command."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason
