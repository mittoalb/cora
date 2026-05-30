"""BC-application-layer errors for the Operation BC.

These errors are raised by application handlers (not domain logic)
and mapped to HTTP / MCP responses by the BC's exception handlers in
`cora/operation/routes.py`.

Domain errors (raised by aggregates / deciders) live with their
aggregate, for example `aggregates/procedure/state.py`.

Distinct class from each other BC's `UnauthorizedError`: each BC
owns its own application-error namespace so an Operation 403 is
distinguishable from other BCs' 403s in logs / aggregator filters
(documented in CONTRIBUTING.md "BC-application-layer errors").
"""


class UnauthorizedError(Exception):
    """The Authorize port denied the command."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class UnknownActionError(Exception):
    """The Conductor was asked to run an action whose name is not registered.

    Application-layer, not domain-layer: a missing registry entry is a
    configuration gap (the deployment didn't wire the action body),
    not an aggregate-invariant violation. Surfaces as a recorded
    `result="failed"` step entry on the Procedure's logbook plus a
    `ConductorFailure` on the result; the caller decides whether to
    abort the Procedure or fix the registry and retry.
    """

    def __init__(self, name: str) -> None:
        super().__init__(f"No action body registered for {name!r}")
        self.name = name
