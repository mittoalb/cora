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


class OverrideKindRequiresParentError(ValueError):
    """`override_kind` was supplied without a `parent_id`.

    A relational rule across two command fields, enforced by the
    decider. Lives at the BC-application layer rather than in
    state.py because no aggregate-state invariant or VO owns it
    (override semantics only make sense when there's something to
    override; either supply both or neither).
    """

    def __init__(self, override_kind: str) -> None:
        super().__init__(f"Decision override_kind={override_kind!r} requires a parent_id")
        self.override_kind = override_kind


class InvalidActorKindForDecisionError(ValueError):
    """The supplied Actor's kind is not permitted for register_decision.

    Raised by the `register_decision` decider when `context.actor.kind`
    is AGENT. Agent-emitted Decisions go through the subscriber path
    (CautionDrafter, RunDebriefer) so the Signer port can sign each
    row at the boundary per [[project_signed_events_design]]; the
    operator-driven register_decision slice stays unsigned and
    human-only.

    Maps to HTTP 400 via the route layer's `Invalid*Error`
    convention. The message is redacted (no internal-architecture
    detail leak) so a non-HTTP caller bypassing route guards sees a
    clean 400.
    """

    def __init__(self, kind: str) -> None:
        super().__init__(f"register_decision cannot accept kind={kind!r} Actors via this slice.")
        self.kind = kind


__all__ = [
    "InvalidActorKindForDecisionError",
    "OverrideKindRequiresParentError",
    "UnauthorizedError",
]
