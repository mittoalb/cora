"""BC-application-layer errors for the Run BC.

These errors are raised by application handlers (not domain logic)
and mapped to HTTP / MCP responses by the BC's exception handlers in
`cora/run/routes.py`.

Domain errors (raised by aggregates / deciders) live with their
aggregate at `aggregates/run/state.py`.

Distinct class from other BCs' `UnauthorizedError` namespaces
(per-BC log-distinguishability convention; see CONTRIBUTING.md
"BC-application-layer errors").
"""


class UnauthorizedError(Exception):
    """The Authorize port denied the command."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason
