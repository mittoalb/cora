"""Application handler for the `re_debrief_run` slice.

Pattern C from the design memo: operator-triggered on-demand
RunDebriefer. The handler is the HTTP-side equivalent of the
subscriber: load Run, build payload (reusing the same prompt
module), call LLM, compose `DecisionRegistered` via the slice's
pure `decide()`, append.

## Differences from the subscriber

  - `principal_id` is the operator's UUID (from HTTP header), NOT
    the agent's. The agent is the WHO of the Decision (`actor_id`);
    the operator is the WHO of the COMMAND (`principal_id`).
  - `decision_id` is a fresh UUIDv7 from the kernel's `IdGenerator`
    (NOT UUID5-derived). Idempotency lives at the HTTP envelope
    via `Idempotency-Key` (Brandur), wrapped at wire.py.
  - `parent_id` is operator-supplied (optional), forming a PROV-O
    `wasInformedBy` chain to the prior auto-fired Debrief.
  - Authorize port IS called (HTTP-handler convention).

## Cross-aggregate validation

The handler pre-loads cross-aggregate refs and reports failures
via aggregate-state errors hoisted from this slice
(cross-BC gate-review):

  - Run aggregate must exist (`load_run` returns non-None);
    raises `cora.run.aggregates.run.state.RunNotFoundError` ->
    HTTP 404 (already-mapped by Run BC's routes).
  - RunDebriefer Agent's Actor must exist and be active; raises
    `AgentNotSeededError` / `AgentDeactivatedError` (both in
    `cora.agent.aggregates.agent.state`) -> HTTP 400.
  - When `parent_decision_id` is supplied: parent Decision must
    exist (`ParentDecisionMissingError` from
    `cora.decision.aggregates.decision`; HTTP 409 per Decision
    BC's existing mapping), have `context == "RunDebrief"`
    (`ParentDecisionAgentMismatchError`; HTTP 400), AND reference
    the same `run_id` in its `decision_inputs`
    (`ParentDecisionRunMismatchError`; HTTP 400).

The parent-context check (PR-author note: architecture gate-review)
catches accidental cross-agent chains where the
operator passes a Decision id authored by a different agent
context (eg. a `PolicyGrant` Decision).

## DebriefDeferred fallback

Same as the subscriber: when the LLM call exhausts, the handler
composes a `DecisionRegistered` with `choice="DebriefDeferred"`
via the same `decide()` and writes it. Operator can retry by
re-issuing the MCP call with a different Idempotency-Key (a same-
key retry replays the cached DebriefDeferred; the operator must
mint a fresh key to bypass the cache).
"""

from typing import Protocol
from uuid import UUID, uuid5

from cora.access.aggregates.actor import load_actor
from cora.agent.aggregates.agent import AgentDeactivatedError, AgentNotSeededError
from cora.agent.errors import UnauthorizedError
from cora.agent.features.re_debrief_run.command import ReDebriefRun
from cora.agent.features.re_debrief_run.context import ReDebriefRunContext
from cora.agent.features.re_debrief_run.decider import decide
from cora.agent.prompts import (
    RunDebriefPayload,
    build_run_debrief_chat_request,
)
from cora.agent.seed import RUN_DEBRIEFER_AGENT_ID, RUN_DEBRIEFER_AGENT_NAME
from cora.agent.subscribers.run_debriefer import redact_secrets
from cora.decision.aggregates.decision import (
    DECISION_CONTEXT_RUN_DEBRIEF,
    ParentDecisionAgentMismatchError,
    ParentDecisionMissingError,
    ParentDecisionRunMismatchError,
    event_type_name,
    load_decision,
    to_payload,
)
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny, LLMError
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.run.aggregates.run import RunNotFoundError, load_run

_STREAM_TYPE = "Decision"
_COMMAND_NAME = "ReDebriefRun"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare re_debrief_run handler -- what `bind()` returns."""

    async def __call__(
        self,
        command: ReDebriefRun,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """re_debrief_run handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: ReDebriefRun,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(deps: Kernel) -> Handler:
    """Build a re_debrief_run handler closed over the shared deps."""
    if deps.llm is None:
        msg = (
            "re_debrief_run handler requires kernel.llm to be set; "
            "configure ANTHROPIC_API_KEY or inject a FakeLLMAdapter."
        )
        raise RuntimeError(msg)
    llm = deps.llm

    async def handler(
        command: ReDebriefRun,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        log = _log.bind(
            command_name=_COMMAND_NAME,
            run_id=str(command.run_id),
            parent_decision_id=(
                str(command.parent_decision_id) if command.parent_decision_id is not None else None
            ),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
        )
        log.info("re_debrief_run.start")

        authz = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(authz, Deny):
            log.info("re_debrief_run.denied", reason=authz.reason)
            raise UnauthorizedError(authz.reason)

        # Pre-load Run aggregate.
        run = await load_run(deps.event_store, command.run_id)
        if run is None:
            raise RunNotFoundError(command.run_id)

        # Pre-load RunDebriefer Agent's Actor and gate on active.
        actor = await load_actor(deps.event_store, RUN_DEBRIEFER_AGENT_ID)
        if actor is None:
            raise AgentNotSeededError(RUN_DEBRIEFER_AGENT_ID, RUN_DEBRIEFER_AGENT_NAME)
        if not actor.is_active:
            raise AgentDeactivatedError(RUN_DEBRIEFER_AGENT_ID)

        # Pre-load parent Decision when ref set; enforce same-agent +
        # same-Run scope.
        if command.parent_decision_id is not None:
            parent = await load_decision(deps.event_store, command.parent_decision_id)
            if parent is None:
                raise ParentDecisionMissingError(command.parent_decision_id)
            parent_context = parent.context.value
            if parent_context != DECISION_CONTEXT_RUN_DEBRIEF:
                raise ParentDecisionAgentMismatchError(
                    command.parent_decision_id,
                    parent_context,
                )
            parent_run_id = _extract_parent_run_id(parent.decision_inputs)
            if parent_run_id != command.run_id:
                raise ParentDecisionRunMismatchError(
                    command.parent_decision_id,
                    parent_run_id,
                )

        new_id = deps.id_generator.new_id()
        now = deps.clock.now()

        payload = RunDebriefPayload(
            terminal_event_type="ReDebriefRun:on-demand",
            terminal_event_reason=None,
            terminal_event_occurred_at=now.isoformat(),
            run_id=command.run_id,
            run_name=run.name.value,
            run_status=str(run.status),
            plan_id=run.plan_id,
            subject_id=run.subject_id,
            campaign_id=run.campaign_id,
            effective_parameters=run.effective_parameters,
            adjustment_count=run.adjustment_count,
            last_adjusted_at=(
                run.last_adjusted_at.isoformat() if run.last_adjusted_at is not None else None
            ),
            interrupted_at=None,
        )
        request = build_run_debrief_chat_request(payload)

        try:
            response = await llm.chat(request)
        except LLMError as exc:
            log.warning(
                "re_debrief_run.llm_failed",
                error_class=type(exc).__name__,
                error_message=redact_secrets(str(exc)[:200]),
            )
            decider_context = ReDebriefRunContext(
                actor=actor,
                choice="DebriefDeferred",
                confidence=None,
                reasoning=(
                    f"LLM call failed with {type(exc).__name__}; on-demand "
                    "re-debrief deferred. Operator may retry with a fresh "
                    "Idempotency-Key to bypass the cached failure."
                ),
                extra_decision_inputs={"failure_error_class": type(exc).__name__},
            )
            outcome = "deferred"
        else:
            decider_context = ReDebriefRunContext(
                actor=actor,
                choice=str(response.parsed["choice"]),
                confidence=(
                    float(response.parsed["confidence"])
                    if response.parsed["confidence"] is not None
                    else None
                ),
                reasoning=str(response.parsed["reasoning"]),
            )
            outcome = "success"

        domain_events = decide(
            state=None,
            command=command,
            context=decider_context,
            now=now,
            new_id=new_id,
        )
        # re_debrief_run's decider always returns exactly one DecisionRegistered;
        # unpack to fail loud if a future maintainer adds a second event.
        (domain_event,) = domain_events
        new_event = to_new_event(
            event_type=event_type_name(domain_event),
            payload=to_payload(domain_event),
            occurred_at=domain_event.occurred_at,
            # Derive event_id from decision_id so the (decision_id,
            # event_id) pair stays stable for downstream observability.
            event_id=uuid5(new_id, "event:0"),
            command_name=_COMMAND_NAME,
            correlation_id=correlation_id,
            causation_id=causation_id,
            principal_id=principal_id,
        )
        await deps.event_store.append(
            stream_type=_STREAM_TYPE,
            stream_id=new_id,
            expected_version=0,
            events=[new_event],
        )

        log.info("re_debrief_run.success", outcome=outcome, decision_id=str(new_id))
        return new_id

    return handler


def _extract_parent_run_id(inputs: dict[str, object] | None) -> UUID | None:
    """Pull `run_id` from the parent Decision's `decision_inputs`.

    Both the subscriber + this handler put `run_id` in
    `decision_inputs` for RunDebrief Decisions, so the same key is
    where the chain link lives. Returns None if absent (which is
    unusual for a RunDebrief Decision but defensive) or malformed.
    The handler treats a None return as a same-Run mismatch
    (parent-run-id != command-run-id), raising
    `ParentDecisionRunMismatchError`.
    """
    if inputs is None:
        return None
    raw = inputs.get("run_id")
    if raw is None:
        return None
    try:
        return UUID(str(raw))
    except ValueError:
        return None
