"""BC-application-layer errors for the Equipment BC.

These errors are raised by application handlers (not domain logic)
and mapped to HTTP / MCP responses by the BC's exception handlers in
`cora/equipment/routes.py`.

Domain errors (raised by aggregates / deciders) live with their
aggregate, for example `aggregates/family/state.py`. Cross-aggregate
shared VOs (Placement, Drawing) live under `aggregates/_*.py` and
keep their error classes co-located in the same module: the tach
layering rule forbids `cora.equipment.aggregates` from depending
on `cora.equipment`, so VO-side error definitions cannot live here
in the BC root.

Distinct class from `cora.access.errors.UnauthorizedError` /
`cora.subject.errors.UnauthorizedError` / `cora.trust.errors.UnauthorizedError`:
each BC owns its own application-error namespace so an Equipment
403 is distinguishable from other BCs' 403s in logs / aggregator
filters (documented in CONTRIBUTING.md "BC-application-layer errors").
Cross-BC consumers catching authorization failures import per-BC.
"""


class UnauthorizedError(Exception):
    """The Authorize port denied the command."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason
