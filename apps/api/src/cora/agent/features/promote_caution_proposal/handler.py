"""Application handler for the `promote_caution_proposal` slice.

Pattern C from the design memo: operator-triggered cross-BC
promotion. Loads the CautionProposal Decision via Decision BC's
read helper, validates via the slice's `decide()`, then dispatches
to Caution BC's `register_caution` or `supersede_caution` slice
depending on the Decision's `choice`.

## Cross-BC write target

Agent BC writes NO events on its own aggregate here. Instead it
invokes Caution BC's existing slices via their `bind(deps)` factory.
This preserves Caution BC's own validation (CautionTarget VOs,
category/severity validation, supersede source-state guard) without
duplication.

## Field mapping (CautionDrafter prompt -> Caution BC command)

The prompt schema generates: `title` (1-200) + `body` (40-2000) +
`tags`. The Caution BC's command expects: `text` + `workaround`
(both REQUIRED). v1 mapping:

  - `text = title` (short summary; appears in Caution.text and the
    Run.start banner truncation)
  - `workaround = body` (the actionable narrative)

## Idempotency

Fresh UUIDv7 per call + Brandur Idempotency-Key envelope wrapped
at wire.py (same pattern as re_debrief_run). Same Idempotency-Key
on retry returns the cached caution_id; fresh key creates a new
Caution.

## Authorize

Authorize port IS called (HTTP-handler convention). Action name
`PromoteCautionProposal`.

## Errors

  - DecisionNotFoundError (404) — load_decision returned None
  - DecisionNotCautionProposalError (400) — wrong context
  - CautionProposalNotActionableError (400) — choice = NoAction
  - CautionProposalMalformedError (400) — proposed_caution invalid
  - UnauthorizedError (403) — Authorize port denied
  - Caution BC's own errors propagate (cross-BC validation)
"""

from typing import Protocol
from uuid import UUID

from cora.agent.errors import UnauthorizedError
from cora.agent.features.promote_caution_proposal.command import PromoteCautionProposal
from cora.agent.features.promote_caution_proposal.decider import decide
from cora.caution.aggregates.caution import (
    AssetTarget,
    CautionCategory,
    CautionSeverity,
    CautionTarget,
    ProcedureTarget,
)
from cora.caution.features.register_caution import RegisterCaution
from cora.caution.features.register_caution import bind as bind_register_caution
from cora.caution.features.supersede_caution import SupersedeCaution
from cora.caution.features.supersede_caution import bind as bind_supersede_caution
from cora.decision.aggregates.decision import load_decision
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny

_COMMAND_NAME = "PromoteCautionProposal"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare promote_caution_proposal handler."""

    async def __call__(
        self,
        command: PromoteCautionProposal,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """promote_caution_proposal handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: PromoteCautionProposal,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def _build_caution_target(target_kind: str, target_id: UUID) -> CautionTarget:
    """Map prompt `target_kind` + `target_id` to Caution BC's union."""
    if target_kind == "Asset":
        return AssetTarget(asset_id=target_id)
    if target_kind == "Procedure":
        return ProcedureTarget(procedure_id=target_id)
    msg = f"Unknown target_kind {target_kind!r}; expected 'Asset' or 'Procedure'"
    raise ValueError(msg)


def bind(deps: Kernel) -> Handler:
    """Build a promote_caution_proposal handler closed over the shared deps."""

    register_handler = bind_register_caution(deps)
    supersede_handler = bind_supersede_caution(deps)

    async def handler(
        command: PromoteCautionProposal,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> UUID:
        log = _log.bind(
            command_name=_COMMAND_NAME,
            decision_id=str(command.decision_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
        )
        log.info("promote_caution_proposal.start")

        authz = await deps.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=_CONDUIT_DEFAULT_ID,
        )
        if isinstance(authz, Deny):
            log.info("promote_caution_proposal.denied", reason=authz.reason)
            raise UnauthorizedError(authz.reason)

        # Load the CautionProposal Decision; the decider validates
        # it + extracts the proposed-Caution payload.
        decision = await load_decision(deps.event_store, command.decision_id)
        view = decide(decision, command)

        target = _build_caution_target(view.target_kind, view.target_id)
        category = CautionCategory(view.category)
        severity = CautionSeverity(view.severity)
        tags = frozenset(view.tags)

        # Dispatch to the appropriate Caution BC slice based on choice.
        caution_id: UUID
        if view.choice == "ProposeSupersede":
            assert view.supersedes_caution_id is not None  # decider invariant
            supersede_command = SupersedeCaution(
                parent_caution_id=view.supersedes_caution_id,
                target=target,
                category=category,
                severity=severity,
                text=view.title,
                workaround=view.body,
                tags=tags,
            )
            log.info(
                "promote_caution_proposal.via_supersede",
                target_kind=view.target_kind,
                prior_caution_id=str(view.supersedes_caution_id),
            )
            caution_id = await supersede_handler(
                supersede_command,
                principal_id=principal_id,
                correlation_id=correlation_id,
                causation_id=causation_id,
            )
        else:
            register_command = RegisterCaution(
                target=target,
                category=category,
                severity=severity,
                text=view.title,
                workaround=view.body,
                tags=tags,
            )
            log.info(
                "promote_caution_proposal.via_register",
                target_kind=view.target_kind,
            )
            caution_id = await register_handler(
                register_command,
                principal_id=principal_id,
                correlation_id=correlation_id,
                causation_id=causation_id,
            )

        log.info(
            "promote_caution_proposal.success",
            choice=view.choice,
            caution_id=str(caution_id),
        )
        return caution_id

    return handler
