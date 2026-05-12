"""BC-application-layer errors for the Decision BC.

These errors are raised by application handlers (not domain logic)
and mapped to HTTP / MCP responses by `cora/decision/routes.py`.
Domain errors live with their aggregate at
`aggregates/decision/state.py`.
"""


class UnauthorizedError(Exception):
    """The Authorize port denied the command."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason
