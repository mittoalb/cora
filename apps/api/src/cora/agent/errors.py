"""BC-application-layer errors for the Agent BC.

These errors are raised by application handlers (not domain logic)
and mapped to HTTP / MCP responses by the BC's exception handlers in
`cora/agent/routes.py`.

Domain errors (raised by aggregates / deciders) live with their
aggregate at `aggregates/agent/state.py`.

Distinct class from each other BC's `UnauthorizedError`: each BC
owns its own application-error namespace so an Agent 403 is
distinguishable from other BCs' 403s in logs / aggregator filters
(documented in CONTRIBUTING.md "BC-application-layer errors").
"""

from uuid import UUID


class UnauthorizedError(Exception):
    """The Authorize port denied the command."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class DecisionNotCautionProposalError(Exception):
    """Operator tried to promote a Decision whose context is not `CautionProposal`.

    Phase 8f-c iter 3. Raised by the `promote_caution_proposal`
    slice when the loaded Decision exists but its context value
    indicates it was authored by a different agent or for a
    different purpose (eg. a `RunDebrief` Decision passed in
    error). Maps to HTTP 400.
    """

    def __init__(self, *, decision_id: UUID, actual_context: str) -> None:
        super().__init__(
            f"Decision {decision_id} has context {actual_context!r}, expected 'CautionProposal'"
        )
        self.decision_id = decision_id
        self.actual_context = actual_context


class CautionProposalNotActionableError(Exception):
    """Operator tried to promote a `NoAction` CautionProposal Decision.

    Phase 8f-c iter 3. `NoAction` is the agent's refusal verdict
    (the Decision exists for audit + telemetry but carries no
    proposed-Caution payload). Maps to HTTP 400.
    """

    def __init__(self, *, decision_id: UUID, choice: str) -> None:
        super().__init__(
            f"Decision {decision_id} has choice {choice!r} which is not "
            "promotable; only Propose{Notice,Caution,Warning,Supersede} are"
        )
        self.decision_id = decision_id
        self.choice = choice


class CautionProposalMalformedError(Exception):
    """The CautionProposal Decision's `inputs.proposed_caution` payload is malformed.

    Phase 8f-c iter 3. Catches schema-violations that the LLM
    structured-output adapter missed (eg. missing required field,
    invalid UUID, ProposeSupersede missing supersedes_caution_id).
    Maps to HTTP 400.
    """

    def __init__(self, *, decision_id: UUID, reason: str) -> None:
        super().__init__(f"Decision {decision_id} proposed_caution payload is malformed: {reason}")
        self.decision_id = decision_id
        self.reason = reason
