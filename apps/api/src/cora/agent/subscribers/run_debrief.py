"""RunDebrief subscriber: CORA's first side-effecting subscriber.

Phase 8f-b iter 2b. Subscribes to the four terminal Run events
(`RunCompleted`, `RunAborted`, `RunStopped`, `RunTruncated`),
loads the terminated Run, asks the LLM for a structured Decision
(choice + confidence + reasoning), and emits one
`DecisionRegistered` per terminal event.

## Side-effecting subscriber pattern (NEW)

The existing projection-worker framework was designed for
read-model writes; the worker's `apply(event, conn)` runs inside
a bookmark-advance transaction with the supplied connection. A
side-effecting subscriber that writes NEW events through the
event store has two challenges:

  1. `PostgresEventStore.append` acquires its own pool connection.
     Decision writes commit in a SEPARATE transaction from the
     bookmark advance. Exact-once is not achievable across these
     two transactions.

  2. The bookmark transaction holds for the duration of `apply()`
     including the LLM call. RunDebrief is `batch_size=1` so the
     transaction holds one connection for ~5-15 s per terminal
     event. Acceptable for pilot scale (~few Runs/day); a watch
     item for facility scale.

Mitigation (1): the Decision's `stream_id` is derived
deterministically from `terminal_event.event_id` via UUIDv5 (see
`_derive_decision_id`). If the bookmark advance fails AFTER the
Decision write succeeds (crash, network, asyncio cancellation),
the event re-fires on the next worker pass and we retry the
Decision write with the SAME `stream_id`. `EventStore.append`
with `expected_version=0` then raises `ConcurrencyError`, which
the subscriber catches and treats as success (the Decision was
already written). At-most-once is preserved.

## DebriefDeferred fallback

When the LLM call fails (after the Anthropic SDK's own internal
retries), the subscriber writes a `DecisionRegistered` with
`choice="DebriefDeferred"` and a reasoning string summarising the
failure. This preserves the exactly-one-Decision-per-terminal-Run
audit invariant (operators can see which Runs the agent couldn't
debrief and decide whether to re-trigger manually).

Per design memo lock #48, the "3 outer retries before
DebriefDeferred" pattern requires cross-`apply()`-call retry-
count tracking (which would need a new persistent table). v1
simplifies to "write DebriefDeferred on the first LLM exhaust".
The Anthropic SDK's `max_retries=2` inside one `apply()` call
gives 3 attempts already; the simplification trades cross-process
retry resilience for implementation simplicity. Watch item for
when operator-rated `misleading` correlates with transient LLM
errors.

## Read scope (v1)

The subscriber loads ONLY the Run aggregate via `load_run`. The
broader read scope (RunReading + ConduitTraversal logbook entries
+ bound Subject/Plan/Method/Practice + acknowledged Cautions +
sibling-Run comparison) is deferred per design memo lock; trigger
is "operators rate v1 Debriefs as misleading citing absent
context".

## Authorize + actor gate

The subscriber does NOT call the `Authorize` port. The agent's
permission to register Decisions is granted at Agent definition
time (8f-a `define_agent` slice's `principal_id` was an admin
who authorised the agent's existence). Per-call authorization is
an HTTP-handler concern; subscribers are internal workers running
under the agent's identity.

The subscriber DOES gate on the agent's `Actor.is_active` flag
(security gate-review P1#1): an operator deactivating the agent's
Actor takes effect on the next `apply()` (the worker reloads the
Actor every pass; an in-flight pass completes). The Agent
aggregate's lifecycle status (Defined / Versioned / Deprecated)
is NOT checked here -- watch item -- because requiring an extra
event-store load per terminal event has measurable cost at
facility scale and the Actor.is_active hop closes the same
revoke-the-agent operator gesture.

## LogbookMirrorPort

If `kernel.logbook_mirror` is set (no production implementor at
8f-b), the subscriber calls `mirror_decision` AFTER the Decision
write commits. Fire-and-forget per the port contract; mirror
errors never propagate.

## API key redaction

The Anthropic SDK error messages may carry the API key in
diagnostic output (defensive against a future SDK regression).
`_redact_secrets` strips `sk-ant-*` substrings from any LLM
error message before structured-logging it (security gate-review
P1#2).

## Duplication-by-design with `re_debrief_run` slice

`_compose_and_append` here and
`cora.agent.features.re_debrief_run.decider.decide` use the same
Decision BC public validators + `DecisionRegistered` constructor.
The subscriber inlines the composition (its at-most-once depends
on a deterministic decision_id derived from terminal_event.event_id
+ a UUID5 namespace, distinct from the operator-triggered slice's
fresh UUIDv7 from the IdGenerator). The slice extracts a pure
`decide()` because the slice-contract test requires `decider.py`.

The shared logic is ~25 lines. **DRY-extract trigger**: when EITHER
a third consumer of the same composition appears (Pattern B per-
anomaly subscriber, second on-demand agent slice at 8f-c+) OR the
subscriber's at-most-once scheme converges with the slice's
(eg. both move to IdempotencyStore-keyed dedup). Pre-trigger: live
with the duplication, documented here + at
`cora.agent.features.re_debrief_run.decider`.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid5

from cora.access.aggregates.actor import load_actor
from cora.agent.prompts import (
    RUN_DEBRIEF_PROMPT_TEMPLATE_ID,
    RunDebriefPayload,
    build_run_debrief_chat_request,
)
from cora.agent.seed import RUN_DEBRIEF_AGENT_ID, RUN_DEBRIEF_AGENT_NAME
from cora.agent.subscribers._terminal_run_helpers import (
    extract_interrupted_at,
    extract_reason,
)
from cora.decision.aggregates.decision import (
    DECISION_CONTEXT_RUN_DEBRIEF,
    DecisionChoice,
    DecisionConfidenceSource,
    DecisionContext,
    DecisionRegistered,
    DecisionRule,
    event_type_name,
    to_payload,
    validate_confidence,
    validate_decision_inputs,
    validate_reasoning,
)
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import ConcurrencyError, LLMError
from cora.run.aggregates.run import load_run

if TYPE_CHECKING:
    from cora.access.aggregates.actor import Actor
    from cora.infrastructure.kernel import Kernel
    from cora.infrastructure.ports import LLMPort, LogbookMirrorPort
    from cora.infrastructure.ports.event_store import EventStore, StoredEvent
    from cora.infrastructure.projection.handler import ConnectionLike

_STREAM_TYPE = "Decision"
_COMMAND_NAME = "RunDebriefSubscriber"
_DECISION_RULE = "agent:RunDebrief:v1"

# Stable namespace for deriving deterministic Decision IDs from
# terminal Run event IDs. UUIDv5(namespace, terminal_event_id) ->
# Decision.stream_id. The namespace is generated once and pinned
# here; changing it invalidates every prior deterministic id (so
# don't).
_RUN_DEBRIEF_DECISION_NAMESPACE = UUID("01900000-0000-7000-8000-0000aaaa0002")

# Terminal Run events this subscriber listens to. The four match
# the design memo lock; iter 2b does NOT include `RunHeld` /
# `RunResumed` (those are mid-lifecycle, not terminal).
_TERMINAL_RUN_EVENTS = frozenset(
    {
        "RunCompleted",
        "RunAborted",
        "RunStopped",
        "RunTruncated",
    }
)

# Regex used to strip Anthropic API-key-shaped substrings from
# error messages before structured-logging them. The key format is
# `sk-ant-` + base64-ish chars; matching aggressively because a
# false-positive redaction (eg. a string that happens to look like
# a key but isn't) costs nothing and a missed redaction costs a
# permanent log-line leak. Security gate-review P1#2.
_API_KEY_LIKE_PATTERN = re.compile(r"sk-ant-[A-Za-z0-9_\-]+")
_REDACTED_TOKEN = "[REDACTED]"

_log = get_logger(__name__)


def redact_secrets(message: str) -> str:
    """Strip Anthropic API-key-like substrings from a log line.

    Defensive: the SDK SHOULD never embed the key in its error
    text, but a future regression that does would persist the key
    to logs forever (events INSERT-only). Sanitise here so the
    redaction is in CORA's audit boundary, not relying on the
    vendor.

    Public callable: used by both this subscriber and the
    `re_debrief_run` handler (8f-c iter 1) for parallel error-
    logging redaction.
    """
    return _API_KEY_LIKE_PATTERN.sub(_REDACTED_TOKEN, message)


# Backward-compat alias retained for the existing test that pins
# the private name. The public name `redact_secrets` is the one
# to use going forward; the alias is dropped at the rule-of-three
# trigger (third consumer or first second-agent ship).
_redact_secrets = redact_secrets


def _derive_decision_id(terminal_event_id: UUID) -> UUID:
    """Deterministic Decision id from terminal event id (UUIDv5).

    Stable across retries so a second `append()` attempt hits
    `expected_version=0` against an existing stream and raises
    `ConcurrencyError`, which the subscriber treats as a no-op.
    """
    return uuid5(_RUN_DEBRIEF_DECISION_NAMESPACE, str(terminal_event_id))


# Extractors hoisted to `_terminal_run_helpers` (rule-of-three);
# imported above as `extract_reason` / `extract_interrupted_at`.


class RunDebriefSubscriber:
    """Side-effecting subscriber: terminal Run -> one advisory Decision.

    Constructed by `make_run_debrief_subscriber` from the Kernel;
    satisfies the `Projection` Protocol (and the `Subscriber`
    primitive it extends) structurally.

    Holds references to the LLM port and event store. The Decision's
    `actor_id` is the seeded RunDebrief Agent's id (== that agent's
    Actor.id per 8f-a's identity-sharing invariant).

    `name` and `subscribed_event_types` are plain class-level
    constants (matches `DecisionRatingsProjection` precedent; the
    `Projection` Protocol declares them as instance attrs which a
    `ClassVar`-annotated class would not satisfy structurally).
    """

    name = "run_debrief"
    subscribed_event_types = _TERMINAL_RUN_EVENTS

    def __init__(
        self,
        *,
        event_store: EventStore,
        llm: LLMPort,
        logbook_mirror: LogbookMirrorPort | None,
    ) -> None:
        self.event_store = event_store
        self.llm = llm
        self.logbook_mirror = logbook_mirror

    async def apply(self, event: StoredEvent, conn: ConnectionLike) -> None:
        """Process one terminal Run event.

        `conn` is the bookmark-advance transaction connection from
        the projection worker. The subscriber does NOT use it for
        Decision writes (those go through `event_store.append`,
        which opens its own transaction). The `conn` is retained
        in the contract for future at-least-once observability
        writes (eg. a `subscriber_attempts` table) but is unused
        at v1.
        """
        _ = conn  # see docstring; not used at v1
        if event.event_type not in _TERMINAL_RUN_EVENTS:
            return  # defensive; worker already filtered

        run_id = UUID(event.payload["run_id"])
        decision_id = _derive_decision_id(event.event_id)
        terminal_event_reason = extract_reason(event)
        interrupted_at = extract_interrupted_at(event)

        log = _log.bind(
            subscriber=self.name,
            command_name=_COMMAND_NAME,
            run_id=str(run_id),
            terminal_event_id=str(event.event_id),
            terminal_event_type=event.event_type,
            derived_decision_id=str(decision_id),
            correlation_id=str(event.correlation_id),
        )
        log.info("run_debrief.start")

        # Load Run aggregate (v1 read scope = Run only).
        run = await load_run(self.event_store, run_id)
        if run is None:
            # Run stream missing despite terminal event for it -- impossible
            # under the normal event-store invariants, but skip cleanly so a
            # corrupt fixture doesn't wedge the bookmark.
            log.warning("run_debrief.skip.run_missing")
            return

        # Pre-load the Agent's Actor (the Decision aggregate requires
        # `actor_id` to exist in Access BC). If the agent isn't seeded
        # (bootstrap not yet run, deployment misconfigured), short-circuit
        # without writing -- the operator needs to fix the seed.
        actor = await load_actor(self.event_store, RUN_DEBRIEF_AGENT_ID)
        if actor is None:
            log.warning(
                "run_debrief.skip.agent_actor_missing",
                agent_id=str(RUN_DEBRIEF_AGENT_ID),
                agent_name=RUN_DEBRIEF_AGENT_NAME,
            )
            return

        # Operator-revocation gate (security gate-review P1#1): a
        # Deactivated Agent Actor must not author new Decisions. The
        # check fires per `apply()`, so a deactivate-while-in-flight
        # only stops the NEXT terminal event; the current one
        # completes. That asymmetry is intentional -- aborting a
        # mid-LLM-call subscriber would orphan the Decision write
        # (LLM cost paid, no audit trail).
        if not actor.is_active:
            log.warning(
                "run_debrief.skip.agent_actor_deactivated",
                agent_id=str(RUN_DEBRIEF_AGENT_ID),
                agent_name=RUN_DEBRIEF_AGENT_NAME,
            )
            return

        payload = RunDebriefPayload(
            terminal_event_type=event.event_type,
            terminal_event_reason=terminal_event_reason,
            terminal_event_occurred_at=event.occurred_at.isoformat(),
            run_id=run_id,
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
            interrupted_at=interrupted_at,
        )
        request = build_run_debrief_chat_request(payload)

        try:
            response = await self.llm.chat(request)
        except LLMError as exc:
            log.warning(
                "run_debrief.llm_failed",
                error_class=type(exc).__name__,
                error_message=redact_secrets(str(exc)[:200]),
            )
            await self._write_debrief_deferred(
                decision_id=decision_id,
                actor=actor,
                run_id=run_id,
                terminal_event=event,
                error_class=type(exc).__name__,
                log=log,
            )
            return

        await self._write_debrief_success(
            decision_id=decision_id,
            actor=actor,
            run_id=run_id,
            terminal_event=event,
            parsed=response.parsed,
            log=log,
        )

        if self.logbook_mirror is not None:
            try:
                await self.logbook_mirror.mirror_decision(
                    decision_id=decision_id,
                    narrative=str(response.parsed.get("reasoning", "")),
                    target_logbook=run.name.value,
                )
            except Exception as exc:
                # Mirror is fire-and-forget per port contract; log but
                # do NOT propagate (mirror outage must not block the
                # Decision-emission audit trail).
                log.warning(
                    "run_debrief.logbook_mirror_failed",
                    error_class=type(exc).__name__,
                    error_message=redact_secrets(str(exc)[:200]),
                )

    async def _write_debrief_success(
        self,
        *,
        decision_id: UUID,
        actor: Actor,
        run_id: UUID,
        terminal_event: StoredEvent,
        parsed: Any,
        log: Any,
    ) -> None:
        """Compose + append the success-path Decision."""
        choice = str(parsed["choice"])
        confidence_raw = parsed["confidence"]
        reasoning_raw = str(parsed["reasoning"])
        await self._compose_and_append(
            decision_id=decision_id,
            actor=actor,
            run_id=run_id,
            terminal_event=terminal_event,
            choice=choice,
            confidence=float(confidence_raw) if confidence_raw is not None else None,
            reasoning=reasoning_raw,
            extra_decision_inputs={},
            outcome="success",
            log=log,
        )

    async def _write_debrief_deferred(
        self,
        *,
        decision_id: UUID,
        actor: Actor,
        run_id: UUID,
        terminal_event: StoredEvent,
        error_class: str,
        log: Any,
    ) -> None:
        """Compose + append the DebriefDeferred fallback Decision.

        Preserves the exactly-one-Decision-per-terminal-Run audit
        invariant when the LLM call exhausts. `confidence` is omitted
        (no LLM probability to report); operators reading the
        Decision know to re-trigger manually.
        """
        await self._compose_and_append(
            decision_id=decision_id,
            actor=actor,
            run_id=run_id,
            terminal_event=terminal_event,
            choice="DebriefDeferred",
            confidence=None,
            reasoning=(
                f"LLM call failed with {error_class}; debrief deferred. "
                "Operator may re-trigger via the agent's MCP tool when "
                "8f-c lands the on-demand path."
            ),
            extra_decision_inputs={"failure_error_class": error_class},
            outcome="deferred",
            log=log,
        )

    async def _compose_and_append(
        self,
        *,
        decision_id: UUID,
        actor: Actor,
        run_id: UUID,
        terminal_event: StoredEvent,
        choice: str,
        confidence: float | None,
        reasoning: str,
        extra_decision_inputs: dict[str, Any],
        outcome: str,
        log: Any,
    ) -> None:
        """Compose `DecisionRegistered` inline and append; catch ConcurrencyError.

        The subscriber doesn't call Decision BC's slice-level
        `decide()` because that handler uses a non-deterministic
        `new_id` (we need UUID5-derived `decision_id` for at-most-
        once retry semantics). Instead it composes the event
        through the same VOs the decider uses (cross-BC import
        boundary respected: only `cora.decision.aggregates` is
        imported, never `cora.decision.features`).

        ConcurrencyError on a deterministic-id stream means a prior
        `apply()` succeeded but the bookmark advance failed; on retry
        the Decision is already there. Treat as success; bookmark
        advances on this pass.

        The Decision's `occurred_at` reuses the terminal event's
        `occurred_at` so successive retries derive the same value
        (deterministic timestamp under retry, no clock port
        consulted).
        """
        # Field validation via Decision BC's public VOs + helpers.
        # Same path the slice's decider takes; the subscriber owns
        # the duplication intentionally per the cross-BC import
        # boundary (no `features.*` import).
        decision_choice = DecisionChoice(choice)
        decision_context = DecisionContext(DECISION_CONTEXT_RUN_DEBRIEF)
        decision_rule = DecisionRule(_DECISION_RULE)
        decision_inputs = validate_decision_inputs(
            {
                "run_id": str(run_id),
                "terminal_event_id": str(terminal_event.event_id),
                "terminal_event_type": terminal_event.event_type,
                "prompt_template_id": str(RUN_DEBRIEF_PROMPT_TEMPLATE_ID),
                **extra_decision_inputs,
            }
        )
        validated_reasoning = validate_reasoning(reasoning)
        validated_confidence = validate_confidence(confidence)

        domain_event = DecisionRegistered(
            decision_id=decision_id,
            actor_id=actor.id,
            context=decision_context.value,
            choice=decision_choice.value,
            parent_id=None,
            override_kind=None,
            decision_rule=decision_rule.value,
            reasoning=validated_reasoning,
            confidence=validated_confidence,
            confidence_source=DecisionConfidenceSource.SELF_REPORTED,
            alternatives=(),
            decision_inputs=decision_inputs,
            reasoning_signature=None,
            occurred_at=terminal_event.occurred_at,
        )

        new_event = to_new_event(
            event_type=event_type_name(domain_event),
            payload=to_payload(domain_event),
            occurred_at=domain_event.occurred_at,
            # Derive event_id deterministically so retries produce
            # the same envelope id (event_store's UNIQUE(event_id)
            # also makes the second write a no-op).
            event_id=uuid5(decision_id, "event:0"),
            command_name=_COMMAND_NAME,
            correlation_id=terminal_event.correlation_id,
            # Causation chain: the agent's Decision is "caused by"
            # the terminal Run event per PROV-O wasInformedBy.
            causation_id=terminal_event.event_id,
            principal_id=actor.id,
        )

        try:
            await self.event_store.append(
                stream_type=_STREAM_TYPE,
                stream_id=decision_id,
                expected_version=0,
                events=[new_event],
            )
        except ConcurrencyError:
            log.info("run_debrief.already_processed", outcome=outcome)
            return

        log.info("run_debrief.success", outcome=outcome)


def make_run_debrief_subscriber(deps: Kernel) -> RunDebriefSubscriber:
    """Construct the subscriber from the Kernel.

    Raises `RuntimeError` if `kernel.llm is None` (the subscriber
    is useless without an LLM). Composition root (`cora.api.main`)
    is responsible for ensuring `llm_factory` is wired before
    register-time. The conditional-registration shim in
    `cora.agent._subscribers.register_agent_subscribers` short-
    circuits with a warning so this only fires for misconfigured
    callers that bypass that shim.
    """
    if deps.llm is None:
        msg = (
            "RunDebriefSubscriber requires kernel.llm to be set; "
            "configure ANTHROPIC_API_KEY or inject a FakeLLMAdapter."
        )
        raise RuntimeError(msg)
    return RunDebriefSubscriber(
        event_store=deps.event_store,
        llm=deps.llm,
        logbook_mirror=deps.logbook_mirror,
    )


__all__ = [
    "RunDebriefSubscriber",
    "make_run_debrief_subscriber",
]
