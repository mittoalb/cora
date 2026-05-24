"""Pure decider for the `PromoteCautionProposal` command.

The decider validates a loaded `Decision` aggregate and returns the
proposed-Caution payload to be applied via cross-BC write. Unlike
most CORA deciders, this one does NOT return event(s) — its job is
to pre-validate a Decision-loaded snapshot + extract the
caller-facing payload. The handler dispatches the cross-BC write
based on `choice` after the decider's check passes.

This shape (validate-and-extract rather than decide-events) is
intentional: the slice writes to a different BC (Caution BC) via
that BC's own decider, so the Agent BC's slice doesn't itself emit
events on any aggregate it owns. The Agent BC's "command" here is
operationally a cross-BC dispatch verb. See
`docs/reference/patterns.md` (Cross-aggregate validation >
Dispatch-slice exception) for the documented variant.

## Validation

  - Decision must not be None -> `DecisionNotFoundError`
  - Decision.context must be `"CautionProposal"`
    -> `DecisionNotCautionProposalError`
  - Decision.choice must NOT be `"NoAction"`
    -> `CautionProposalNotActionableError`
  - When choice is `ProposeSupersede`, `proposed_caution.supersedes_caution_id`
    must be present -> `CautionProposalMalformedError`
  - `proposed_caution` payload must be present in `inputs`
    -> `CautionProposalMalformedError`
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from cora.agent.errors import (
    CautionProposalMalformedError,
    CautionProposalNotActionableError,
    DecisionNotCautionProposalError,
)
from cora.agent.features.promote_caution_proposal.command import PromoteCautionProposal
from cora.decision.aggregates.decision import (
    DECISION_CONTEXT_CAUTION_PROPOSAL,
    Decision,
    DecisionNotFoundError,
)


@dataclass(frozen=True)
class ProposedCautionView:
    """Read-only view of the proposed-Caution payload + dispatch hint.

    Returned by `decide` to the handler so it can route to the
    right Caution BC slice (`register_caution` or `supersede_caution`).
    """

    decision_id: UUID
    choice: str  # ProposeNotice | ProposeCaution | ProposeWarning | ProposeSupersede
    target_kind: str  # "Asset" | "Procedure"
    target_id: UUID
    category: str
    severity: str
    title: str
    body: str
    tags: tuple[str, ...]
    supersedes_caution_id: UUID | None


def decide(state: Decision | None, command: PromoteCautionProposal) -> ProposedCautionView:
    """Validate a CautionProposal Decision and extract the proposed payload.

    Invariants:
      - Decision must not be None -> DecisionNotFoundError
      - Decision.context must be "CautionProposal"
        -> DecisionNotCautionProposalError
      - Decision.choice must not be "NoAction"
        -> CautionProposalNotActionableError
      - inputs must carry a dict-shaped `proposed_caution` payload
        with required fields -> CautionProposalMalformedError
      - target_id must be a valid UUID
        -> CautionProposalMalformedError
      - tags must be a list of strings
        -> CautionProposalMalformedError
      - When choice is ProposeSupersede, `supersedes_caution_id`
        must be present + valid UUID
        -> CautionProposalMalformedError
      - When choice is not ProposeSupersede,
        `supersedes_caution_id` must be absent
        -> CautionProposalMalformedError
    """
    if state is None:
        raise DecisionNotFoundError(command.decision_id)

    if state.context.value != DECISION_CONTEXT_CAUTION_PROPOSAL:
        raise DecisionNotCautionProposalError(
            decision_id=command.decision_id,
            actual_context=state.context.value,
        )

    choice = state.choice.value
    if choice == "NoAction":
        raise CautionProposalNotActionableError(
            decision_id=command.decision_id,
            choice=choice,
        )

    inputs: dict[str, Any] = dict(state.inputs) if state.inputs else {}
    proposed: Any = inputs.get("proposed_caution")
    if proposed is None or not isinstance(proposed, dict):
        raise CautionProposalMalformedError(
            decision_id=command.decision_id,
            reason="missing or non-dict `proposed_caution` payload",
        )

    try:
        target_kind = str(proposed["target_kind"])
        target_id_raw = str(proposed["target_id"])
        category = str(proposed["category"])
        severity = str(proposed["severity"])
        title = str(proposed["title"])
        body = str(proposed["body"])
        tags_raw = proposed.get("tags", [])
        if not isinstance(tags_raw, list):
            raise CautionProposalMalformedError(
                decision_id=command.decision_id,
                reason="`tags` must be a list of strings",
            )
        tags = tuple(str(t) for t in tags_raw)
    except KeyError as exc:
        raise CautionProposalMalformedError(
            decision_id=command.decision_id,
            reason=f"missing required proposed-Caution field: {exc.args[0]!r}",
        ) from exc

    try:
        target_id = UUID(target_id_raw)
    except ValueError as exc:
        raise CautionProposalMalformedError(
            decision_id=command.decision_id,
            reason=f"`target_id` is not a valid UUID: {target_id_raw!r}",
        ) from exc

    supersedes_caution_id: UUID | None = None
    sup_raw = proposed.get("supersedes_caution_id")
    if choice == "ProposeSupersede":
        if sup_raw is None:
            raise CautionProposalMalformedError(
                decision_id=command.decision_id,
                reason="ProposeSupersede requires non-null `supersedes_caution_id`",
            )
        try:
            supersedes_caution_id = UUID(str(sup_raw))
        except ValueError as exc:
            raise CautionProposalMalformedError(
                decision_id=command.decision_id,
                reason=f"`supersedes_caution_id` is not a valid UUID: {sup_raw!r}",
            ) from exc
    elif sup_raw is not None:
        # Cross-check: only ProposeSupersede should carry this field.
        # Treat as malformed if other choices include it (the LLM
        # confused the choice with the action).
        raise CautionProposalMalformedError(
            decision_id=command.decision_id,
            reason=(
                f"`supersedes_caution_id` set but choice is {choice!r}; "
                "supersede field is only valid with ProposeSupersede"
            ),
        )

    return ProposedCautionView(
        decision_id=command.decision_id,
        choice=choice,
        target_kind=target_kind,
        target_id=target_id,
        category=category,
        severity=severity,
        title=title,
        body=body,
        tags=tags,
        supersedes_caution_id=supersedes_caution_id,
    )
