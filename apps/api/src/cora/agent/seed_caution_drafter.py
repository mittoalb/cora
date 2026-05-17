"""Bootstrap-time seed for the CautionDrafter Agent.

Phase 8f-c iter 3. The CautionDrafter subscriber needs an Agent
record (and its co-registered Actor) to exist at the pinned
`CAUTION_DRAFTER_AGENT_ID` so it can set `Decision.actor_id` without
a lookup. Mirrors `cora.agent.seed.seed_run_debrief_agent` verbatim
except for the constants (id / name / kind / version / description /
prompt-template-id / default model).

Per [[project-caution-drafter-design]] Locks:
  - Pinned UUID in the `bbbb00XX` range (sibling-to-`aaaa00XX`
    RunDebrief range); deployment-stable forever.
  - Atomic cross-BC write of `ActorRegistered(kind="agent")` +
    `AgentDefined` via `EventStore.append_streams`.
  - Envelope's `principal_id = SYSTEM_PRINCIPAL_ID` (NOT
    self-reference; agent doesn't exist yet at boot).
  - `ConcurrencyError`-as-no-op for restart idempotency.
  - Default model = `claude-sonnet-4-6` (CautionDrafter's task is
    more nuanced than RunDebrief's classification; warrants Sonnet
    over Haiku).
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
from cora.agent.prompts.caution_drafter import (
    CAUTION_DRAFTER_PROMPT_TEMPLATE_ID,
    DEFAULT_CAUTION_DRAFTER_MODEL,
)
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import ConcurrencyError
from cora.infrastructure.ports.event_store import StreamAppend
from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel


# ---------------------------------------------------------------------------
# CautionDrafter agent identity (deployment-stable constants)
# ---------------------------------------------------------------------------

# Treat as FOREVER-STABLE. Same change-cost rationale as
# `RUN_DEBRIEF_AGENT_ID`: changing this orphans every prior
# CautionDrafter-authored Decision and breaks the subscriber's
# deterministic decision_id derivation.
#
# UUID is in the deployment-controlled `bbbb00XX` range (sibling
# to RunDebrief's `aaaa00XX` range). Future agents (#3+) get their
# own `ccccc00XX` / `dddd00XX` / etc. ranges so the bootstrap
# constants stay visually grouped per agent.
CAUTION_DRAFTER_AGENT_ID = UUID("01900000-0000-7000-8000-0000bbbb0010")
CAUTION_DRAFTER_AGENT_NAME = "CautionDrafter"
CAUTION_DRAFTER_AGENT_KIND = "CautionDrafter"
CAUTION_DRAFTER_AGENT_VERSION = "1.0.0"
CAUTION_DRAFTER_AGENT_DESCRIPTION = (
    "Advisory LLM agent: subscribes to terminal Run events and emits one "
    "Decision(context=CautionProposal) per event with a closed 5-choice "
    "verdict (NoAction / ProposeNotice / ProposeCaution / ProposeWarning / "
    "ProposeSupersede) + proposed-Caution payload. Operator promotes via "
    "promote_caution_proposal slice. Never writes Cautions directly."
)


# ---------------------------------------------------------------------------
# Deterministic IDs for the bootstrap write envelope
# ---------------------------------------------------------------------------

_AGENT_EVENT_ID = UUID("01900000-0000-7000-8000-0000bbbb0012")
_ACTOR_EVENT_ID = UUID("01900000-0000-7000-8000-0000bbbb0013")
_BOOTSTRAP_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000bbbb0014")

_log = get_logger(__name__)


async def seed_caution_drafter_agent(kernel: Kernel) -> None:
    """Seed the CautionDrafter Agent + co-registered Actor (idempotent).

    No-op if the agent is already seeded; logs the outcome either
    way. Safe to call on every app boot.
    """
    from cora.infrastructure.event_envelope import to_new_event

    now = kernel.clock.now()

    name = AgentName(CAUTION_DRAFTER_AGENT_NAME)
    kind = AgentKind(CAUTION_DRAFTER_AGENT_KIND)
    version = AgentVersion(CAUTION_DRAFTER_AGENT_VERSION)
    description = AgentDescription(CAUTION_DRAFTER_AGENT_DESCRIPTION)
    model_ref = ModelRef(
        provider=DEFAULT_CAUTION_DRAFTER_MODEL.provider,
        model=DEFAULT_CAUTION_DRAFTER_MODEL.model,
        snapshot_pin=DEFAULT_CAUTION_DRAFTER_MODEL.snapshot_pin,
    )

    agent_event = AgentDefined(
        agent_id=CAUTION_DRAFTER_AGENT_ID,
        kind=kind.value,
        name=name.value,
        version=version.value,
        model_ref=model_ref,
        description=description.value,
        canonical_uri=None,
        prompt_template_id=CAUTION_DRAFTER_PROMPT_TEMPLATE_ID,
        capabilities=frozenset(),
        occurred_at=now,
    )
    actor_event = ActorRegistered(
        actor_id=CAUTION_DRAFTER_AGENT_ID,
        name=name.value,
        occurred_at=now,
        kind=ActorKind.AGENT,
    )

    agent_new_event = to_new_event(
        event_type=event_type_name(agent_event),
        payload=to_payload(agent_event),
        occurred_at=now,
        event_id=_AGENT_EVENT_ID,
        command_name="SeedCautionDrafterAgent",
        correlation_id=_BOOTSTRAP_CORRELATION_ID,
        causation_id=None,
        principal_id=SYSTEM_PRINCIPAL_ID,
    )
    actor_new_event = to_new_event(
        event_type=actor_event_type_name(actor_event),
        payload=actor_to_payload(actor_event),
        occurred_at=now,
        event_id=_ACTOR_EVENT_ID,
        command_name="SeedCautionDrafterAgent",
        correlation_id=_BOOTSTRAP_CORRELATION_ID,
        causation_id=None,
        principal_id=SYSTEM_PRINCIPAL_ID,
    )

    try:
        await kernel.event_store.append_streams(
            [
                StreamAppend(
                    stream_type="Actor",
                    stream_id=CAUTION_DRAFTER_AGENT_ID,
                    expected_version=0,
                    events=[actor_new_event],
                ),
                StreamAppend(
                    stream_type="Agent",
                    stream_id=CAUTION_DRAFTER_AGENT_ID,
                    expected_version=0,
                    events=[agent_new_event],
                ),
            ]
        )
    except ConcurrencyError:
        _log.info(
            "agent_seed.already_present",
            agent_id=str(CAUTION_DRAFTER_AGENT_ID),
            agent_name=CAUTION_DRAFTER_AGENT_NAME,
        )
        return

    _log.info(
        "agent_seed.created",
        agent_id=str(CAUTION_DRAFTER_AGENT_ID),
        agent_name=CAUTION_DRAFTER_AGENT_NAME,
        kind=kind.value,
        version=version.value,
    )


__all__ = [
    "CAUTION_DRAFTER_AGENT_DESCRIPTION",
    "CAUTION_DRAFTER_AGENT_ID",
    "CAUTION_DRAFTER_AGENT_KIND",
    "CAUTION_DRAFTER_AGENT_NAME",
    "CAUTION_DRAFTER_AGENT_VERSION",
    "seed_caution_drafter_agent",
]
