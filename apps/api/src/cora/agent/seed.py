"""Bootstrap-time seed for the RunDebriefer Agent.

The RunDebriefer subscriber needs an Agent record (and its
co-registered Actor) to exist at the pinned
`RUN_DEBRIEFER_AGENT_ID` so it can set `Decision.actor_id` without
a lookup. This module provides:

  - The deployment-stable identity constants (`RUN_DEBRIEFER_AGENT_ID`
    + name / kind / version / description). Hosted here -- not in
    the Agent aggregate's `state.py` -- because they are deployment
    seed config, not aggregate-invariant declarations. Per cross-BC
    gate-review convention.
  - The `seed_run_debriefer_agent(kernel)` callable invoked from the
    FastAPI lifespan AFTER `build_kernel` returns the Kernel.

## Why a fixed UUID

Most CORA aggregates get server-allocated UUIDv7 ids. The
RunDebriefer agent is a singleton-per-deployment whose id is
referenced by the subscriber + the deterministic decision-id
derivation. Pinning the id to a constant ([[project_run_debrief_design]]
lock #50) lets the bootstrap re-run safely on every restart
(idempotent UPSERT-like semantics via `expected_version=0` ->
ConcurrencyError) without needing a "find or create" lookup.

## Idempotency

The seed calls `event_store.append_streams` with
`expected_version=0` on BOTH streams. If the agent was already
seeded on a prior boot, the append raises `ConcurrencyError`
(streams exist at version > 0), which the seed catches and
treats as success. Mirrors the subscriber's deterministic-
id-with-ConcurrencyError-as-no-op pattern.

## Principal_id

The bootstrap envelope uses `SYSTEM_PRINCIPAL_ID`, NOT the
agent's own id. The agent doesn't exist yet at boot-time, so
self-attribution would be a circular-causation lie in the event
envelope. `SYSTEM_PRINCIPAL_ID` is the conventional value for
"the system did this before any human auth context existed"
writes; the seed is one such write. Per security gate-review
convention.

## Wiring

Called from the FastAPI lifespan after `build_kernel` and after
the Postgres pool is alive. If `kernel.event_store` is in-memory
(test mode), the seed still runs and writes to memory; tests can
opt out by not calling the seed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from cora.access.aggregates.actor import (
    ActorKind,
    ActorRegistered,
)
from cora.access.aggregates.actor import event_type_name as actor_event_type_name
from cora.access.aggregates.actor import to_payload as actor_to_payload
from cora.agent.aggregates.agent import (
    AgentDefined,
    AgentDescription,
    AgentKind,
    AgentName,
    AgentVersion,
    ModelRef,
    event_type_name,
    to_payload,
)
from cora.agent.prompts import RUN_DEBRIEF_PROMPT_TEMPLATE_ID
from cora.agent.prompts.run_debrief import DEFAULT_RUN_DEBRIEF_MODEL
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import ConcurrencyError
from cora.infrastructure.ports.event_store import StreamAppend
from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel


# ---------------------------------------------------------------------------
# RunDebriefer agent identity (deployment-stable constants)
# ---------------------------------------------------------------------------

# Treat as FOREVER-STABLE. Changing this id would:
#   - Orphan every prior RunDebriefer-authored Decision (their
#     actor_id pointers go stale).
#   - Break the subscriber's deterministic decision_id derivation
#     for events already processed.
#   - Require a manual migration to re-assign actor_id on every
#     historical RunDebriefer Decision.
# The id is in the deployment-controlled `aaaa00XX` UUID range
# alongside other RunDebriefer-related constants (prompt template id,
# decision-id namespace, bootstrap event ids); see the registry
# table in the file-level comment of `cora.agent.prompts.run_debrief`
# for the allocation scheme.
RUN_DEBRIEFER_AGENT_ID = UUID("01900000-0000-7000-8000-0000aaaa0010")
RUN_DEBRIEFER_AGENT_NAME = "RunDebriefer"
RUN_DEBRIEFER_AGENT_KIND = "RunDebriefer"
RUN_DEBRIEFER_AGENT_VERSION = "1.0.0"
RUN_DEBRIEFER_AGENT_DESCRIPTION = (
    "Advisory LLM agent: writes one Decision per terminal Run event with a "
    "closed-set choice + 130-230 word BLUF + 4-section AAR narrative. "
    "Observer-only; never gates Run state."
)


# ---------------------------------------------------------------------------
# Deterministic IDs for the bootstrap write envelope
# ---------------------------------------------------------------------------

# Each event's event_id is deterministic so a retried seed attempt
# produces the same envelope id (event_store UNIQUE constraint on
# event_id makes the second attempt a no-op even if ConcurrencyError
# didn't catch first).
_AGENT_EVENT_ID = UUID("01900000-0000-7000-8000-0000aaaa0012")
_ACTOR_EVENT_ID = UUID("01900000-0000-7000-8000-0000aaaa0013")
_BOOTSTRAP_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000aaaa0014")

_log = get_logger(__name__)


async def seed_run_debriefer_agent(kernel: Kernel) -> None:
    """Seed the RunDebriefer Agent + co-registered Actor (idempotent).

    No-op if the agent is already seeded; logs the outcome either
    way. Safe to call on every app boot.
    """
    from cora.infrastructure.event_envelope import to_new_event

    now = kernel.clock.now()

    # Validate the constants by routing them through the same VOs
    # the decider uses. If a constant is invalid (eg. too long) we
    # crash at startup with a clear error.
    name = AgentName(RUN_DEBRIEFER_AGENT_NAME)
    kind = AgentKind(RUN_DEBRIEFER_AGENT_KIND)
    version = AgentVersion(RUN_DEBRIEFER_AGENT_VERSION)
    description = AgentDescription(RUN_DEBRIEFER_AGENT_DESCRIPTION)
    # ModelRef instance from prompts module; re-validate by passing
    # through the VO constructor.
    model_ref = ModelRef(
        provider=DEFAULT_RUN_DEBRIEF_MODEL.provider,
        model=DEFAULT_RUN_DEBRIEF_MODEL.model,
        snapshot_pin=DEFAULT_RUN_DEBRIEF_MODEL.snapshot_pin,
    )

    agent_event = AgentDefined(
        agent_id=RUN_DEBRIEFER_AGENT_ID,
        kind=kind.value,
        name=name.value,
        version=version.value,
        model_ref=model_ref,
        description=description.value,
        canonical_uri=None,
        prompt_template_id=RUN_DEBRIEF_PROMPT_TEMPLATE_ID,
        capabilities=frozenset(),
        occurred_at=now,
    )
    actor_event = ActorRegistered(
        actor_id=RUN_DEBRIEFER_AGENT_ID,
        name=name.value,
        occurred_at=now,
        kind=ActorKind.AGENT,
    )

    agent_new_event = to_new_event(
        event_type=event_type_name(agent_event),
        payload=to_payload(agent_event),
        occurred_at=now,
        event_id=_AGENT_EVENT_ID,
        command_name="SeedRunDebrieferAgent",
        correlation_id=_BOOTSTRAP_CORRELATION_ID,
        causation_id=None,
        principal_id=SYSTEM_PRINCIPAL_ID,
    )
    actor_new_event = to_new_event(
        event_type=actor_event_type_name(actor_event),
        payload=actor_to_payload(actor_event),
        occurred_at=now,
        event_id=_ACTOR_EVENT_ID,
        command_name="SeedRunDebrieferAgent",
        correlation_id=_BOOTSTRAP_CORRELATION_ID,
        causation_id=None,
        principal_id=SYSTEM_PRINCIPAL_ID,
    )

    try:
        await kernel.event_store.append_streams(
            [
                StreamAppend(
                    stream_type="Actor",
                    stream_id=RUN_DEBRIEFER_AGENT_ID,
                    expected_version=0,
                    events=[actor_new_event],
                ),
                StreamAppend(
                    stream_type="Agent",
                    stream_id=RUN_DEBRIEFER_AGENT_ID,
                    expected_version=0,
                    events=[agent_new_event],
                ),
            ]
        )
    except ConcurrencyError:
        _log.info(
            "agent_seed.already_present",
            agent_id=str(RUN_DEBRIEFER_AGENT_ID),
            agent_name=RUN_DEBRIEFER_AGENT_NAME,
        )
        return

    _log.info(
        "agent_seed.created",
        agent_id=str(RUN_DEBRIEFER_AGENT_ID),
        agent_name=RUN_DEBRIEFER_AGENT_NAME,
        kind=kind.value,
        version=version.value,
    )


__all__ = [
    "RUN_DEBRIEFER_AGENT_DESCRIPTION",
    "RUN_DEBRIEFER_AGENT_ID",
    "RUN_DEBRIEFER_AGENT_KIND",
    "RUN_DEBRIEFER_AGENT_NAME",
    "RUN_DEBRIEFER_AGENT_VERSION",
    "seed_run_debriefer_agent",
]
