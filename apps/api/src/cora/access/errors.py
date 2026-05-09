"""BC-application-layer errors for the Access BC.

These errors are raised by application handlers (not domain logic) and
mapped to HTTP / MCP responses by the BC's exception handlers in
`cora/access/routes.py`.

Domain errors (raised by aggregates / deciders) live with their
aggregate, e.g. `aggregates/actor/state.py`.
"""


class UnauthorizedError(Exception):
    """The Authorize port denied the command."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason
