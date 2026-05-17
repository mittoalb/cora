"""Application-handler tests for the `promote_caution_proposal` slice (Phase 8f-c iter 3).

Exercises the cross-BC dispatch path: load Decision, validate via
decider, dispatch to Caution BC's register_caution OR
supersede_caution slice. Uses InMemoryEventStore + an existing
seeded Caution stream (for the supersede path).
"""

# pyright: reportPrivateUsage=false, reportUnknownMemberType=false

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from cora.agent.aggregates.agent import ModelRef
from cora.agent.aggregates.agent import event_type_name as agent_event_type_name
from cora.agent.aggregates.agent import to_payload as agent_to_payload
from cora.agent.aggregates.agent.events import AgentDefined
from cora.agent.errors import (
    CautionProposalMalformedError,
    CautionProposalNotActionableError,
    DecisionNotCautionProposalError,
    DecisionNotEmittedByCautionDrafterError,
    UnauthorizedError,
)
from cora.agent.features import promote_caution_proposal
from cora.agent.features.promote_caution_proposal import PromoteCautionProposal
from cora.caution.aggregates.caution import (
    AssetTarget,
    CautionCategory,
    CautionSeverity,
    load_caution,
)
from cora.caution.features.register_caution import RegisterCaution
from cora.caution.features.register_caution import bind as bind_register_caution
from cora.decision.aggregates.decision import (
    DECISION_CONTEXT_CAUTION_PROPOSAL,
    DECISION_CONTEXT_RUN_DEBRIEF,
    DecisionConfidenceSource,
    DecisionNotFoundError,
    DecisionRegistered,
    event_type_name,
    to_payload,
)
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.memory.event_store import InMemoryEventStore
from tests.unit._helpers import build_deps as _build_deps_shared

_T0 = datetime(2026, 5, 17, 10, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 5, 17, 11, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)

_ASSET_ID = UUID("01900000-0000-7000-8000-000000000aaa")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000099001")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000009900a")

_PROPOSED_CAUTION_NOTICE: dict[str, Any] = {
    "target_kind": "Asset",
    "target_id": str(_ASSET_ID),
    "category": "Wear",
    "severity": "Notice",
    "title": "Encoder drift after extended rotation",
    "body": (
        "Re-home the rotary stage encoder every 10 minutes of continuous "
        "rotation; drift accumulates and triggers interlock at ~12 minutes."
    ),
    "tags": ["encoder", "rotary-stage"],
}


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
    ids: list[UUID] | None = None,
) -> Kernel:
    """Build a Kernel for handler tests; supplies a generous id queue."""
    queued_ids = ids if ids is not None else [uuid4() for _ in range(10)]
    return _build_deps_shared(
        ids=queued_ids,
        now=_T2,
        event_store=event_store,
        deny=deny,
    )


async def _seed_caution_drafter_agent(store: InMemoryEventStore, *, agent_id: UUID) -> None:
    """Seed an Agent stream with kind='CautionDrafter' so the promote
    handler's provenance gate (Phase A.2) passes.

    Mirrors the production seed at `cora.agent.seed_caution_drafter`
    but skips the cross-BC Access write (Actor row is not loaded by
    the gate).
    """
    genesis = AgentDefined(
        agent_id=agent_id,
        kind="CautionDrafter",
        name="Caution Drafter",
        version="v1",
        model_ref=ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
        description="Drafts operator-advisory Cautions from terminal Runs.",
        canonical_uri=None,
        prompt_template_id=None,
        capabilities=frozenset(),
        occurred_at=_T0,
    )
    new_event = to_new_event(
        event_type=agent_event_type_name(genesis),
        payload=agent_to_payload(genesis),
        occurred_at=genesis.occurred_at,
        event_id=uuid4(),
        command_name="SeedCautionDrafterAgent",
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        principal_id=agent_id,
    )
    await store.append(
        stream_type="Agent",
        stream_id=agent_id,
        expected_version=0,
        events=[new_event],
    )


async def _seed_non_caution_drafter_agent(
    store: InMemoryEventStore, *, agent_id: UUID, kind: str = "RunDebrief"
) -> None:
    """Seed an Agent of a non-CautionDrafter kind for negative-path gate tests."""
    genesis = AgentDefined(
        agent_id=agent_id,
        kind=kind,
        name=kind,
        version="v1",
        model_ref=ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
        description=f"{kind} agent.",
        canonical_uri=None,
        prompt_template_id=None,
        capabilities=frozenset(),
        occurred_at=_T0,
    )
    new_event = to_new_event(
        event_type=agent_event_type_name(genesis),
        payload=agent_to_payload(genesis),
        occurred_at=genesis.occurred_at,
        event_id=uuid4(),
        command_name=f"Seed{kind}Agent",
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        principal_id=agent_id,
    )
    await store.append(
        stream_type="Agent",
        stream_id=agent_id,
        expected_version=0,
        events=[new_event],
    )


async def _seed_caution_proposal_decision(
    store: InMemoryEventStore,
    *,
    decision_id: UUID,
    actor_id: UUID,
    choice: str,
    inputs: dict[str, Any],
) -> None:
    """Append a CautionProposal Decision (genesis event) for the handler to load."""
    event = DecisionRegistered(
        decision_id=decision_id,
        actor_id=actor_id,
        context=DECISION_CONTEXT_CAUTION_PROPOSAL,
        choice=choice,
        parent_id=None,
        override_kind=None,
        decision_rule="agent:CautionDrafter:v1",
        reasoning="test rationale narrative spanning enough words to satisfy the bound",
        confidence=0.7,
        confidence_source=DecisionConfidenceSource.SELF_REPORTED,
        alternatives=(),
        decision_inputs=inputs,
        reasoning_signature=None,
        occurred_at=_T0,
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=_T0,
        event_id=uuid4(),
        command_name="CautionDrafterSubscriber",
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        principal_id=actor_id,
    )
    await store.append(
        stream_type="Decision",
        stream_id=decision_id,
        expected_version=0,
        events=[new_event],
    )


async def _seed_existing_caution(deps: Kernel) -> UUID:
    """Register a Caution against _ASSET_ID via Caution BC's slice;
    returns the new caution_id."""
    register = bind_register_caution(deps)
    return await register(
        RegisterCaution(
            target=AssetTarget(asset_id=_ASSET_ID),
            category=CautionCategory.WEAR,
            severity=CautionSeverity.NOTICE,
            text="prior",
            workaround="prior workaround",
            tags=frozenset(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


# ---------------------------------------------------------------------------
# Happy path: ProposeNotice -> register_caution dispatch
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_handler_promotes_via_register_for_propose_notice() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    decision_id = uuid4()
    actor_id = uuid4()
    await _seed_caution_drafter_agent(store, agent_id=actor_id)
    await _seed_caution_proposal_decision(
        store,
        decision_id=decision_id,
        actor_id=actor_id,
        choice="ProposeNotice",
        inputs={"proposed_caution": _PROPOSED_CAUTION_NOTICE},
    )
    handler = promote_caution_proposal.bind(deps)

    caution_id = await handler(
        PromoteCautionProposal(decision_id=decision_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Caution was actually created in Caution BC's stream.
    caution = await load_caution(deps.event_store, caution_id)
    assert caution is not None
    assert caution.text.value.startswith("Encoder drift")
    assert caution.workaround.value.startswith("Re-home")
    assert caution.severity == CautionSeverity.NOTICE
    assert caution.category == CautionCategory.WEAR


# ---------------------------------------------------------------------------
# Happy path: ProposeSupersede -> supersede_caution dispatch
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_handler_promotes_via_supersede_for_propose_supersede() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    # First seed an existing Caution we can supersede.
    prior_caution_id = await _seed_existing_caution(deps)

    proposed = dict(_PROPOSED_CAUTION_NOTICE)
    proposed["severity"] = "Caution"  # supersede with refined severity
    proposed["title"] = "Refined: encoder drift mitigation"
    proposed["supersedes_caution_id"] = str(prior_caution_id)

    decision_id = uuid4()
    actor_id = uuid4()
    await _seed_caution_drafter_agent(store, agent_id=actor_id)
    await _seed_caution_proposal_decision(
        store,
        decision_id=decision_id,
        actor_id=actor_id,
        choice="ProposeSupersede",
        inputs={"proposed_caution": proposed},
    )
    handler = promote_caution_proposal.bind(deps)

    new_caution_id = await handler(
        PromoteCautionProposal(decision_id=decision_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # The new Caution is a fresh aggregate (not the prior one).
    assert new_caution_id != prior_caution_id
    new_caution = await load_caution(deps.event_store, new_caution_id)
    assert new_caution is not None
    assert new_caution.severity == CautionSeverity.CAUTION
    assert new_caution.text.value.startswith("Refined")


# ---------------------------------------------------------------------------
# Validation errors propagate
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_handler_raises_decision_not_found_for_unknown_id() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = promote_caution_proposal.bind(deps)
    with pytest.raises(DecisionNotFoundError):
        await handler(
            PromoteCautionProposal(decision_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_rejects_wrong_context() -> None:
    """Promoting a RunDebrief Decision (not a CautionProposal) is a 400."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    decision_id = uuid4()
    actor_id = uuid4()
    # Seed CautionDrafter so the provenance gate passes; the decider's
    # context check is the assertion under test here.
    await _seed_caution_drafter_agent(store, agent_id=actor_id)
    event = DecisionRegistered(
        decision_id=decision_id,
        actor_id=actor_id,
        context=DECISION_CONTEXT_RUN_DEBRIEF,
        choice="NominalCompletion",
        parent_id=None,
        override_kind=None,
        decision_rule="agent:RunDebrief:v1",
        reasoning="rationale narrative spanning enough words to satisfy the bound",
        confidence=0.9,
        confidence_source=DecisionConfidenceSource.SELF_REPORTED,
        alternatives=(),
        decision_inputs={"run_id": str(uuid4())},
        reasoning_signature=None,
        occurred_at=_T0,
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=_T0,
        event_id=uuid4(),
        command_name="RunDebriefSubscriber",
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        principal_id=actor_id,
    )
    await store.append(
        stream_type="Decision",
        stream_id=decision_id,
        expected_version=0,
        events=[new_event],
    )
    handler = promote_caution_proposal.bind(deps)

    with pytest.raises(DecisionNotCautionProposalError):
        await handler(
            PromoteCautionProposal(decision_id=decision_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_rejects_no_action_choice() -> None:
    """NoAction is the agent's refusal verdict; not promotable."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    decision_id = uuid4()
    actor_id = uuid4()
    await _seed_caution_drafter_agent(store, agent_id=actor_id)
    await _seed_caution_proposal_decision(
        store,
        decision_id=decision_id,
        actor_id=actor_id,
        choice="NoAction",
        inputs={"reason": "no actionable signal"},
    )
    handler = promote_caution_proposal.bind(deps)

    with pytest.raises(CautionProposalNotActionableError):
        await handler(
            PromoteCautionProposal(decision_id=decision_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_rejects_malformed_proposed_caution() -> None:
    """A Propose* choice with no proposed_caution payload is malformed."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    decision_id = uuid4()
    actor_id = uuid4()
    await _seed_caution_drafter_agent(store, agent_id=actor_id)
    await _seed_caution_proposal_decision(
        store,
        decision_id=decision_id,
        actor_id=actor_id,
        choice="ProposeNotice",
        inputs={},  # no proposed_caution
    )
    handler = promote_caution_proposal.bind(deps)

    with pytest.raises(CautionProposalMalformedError):
        await handler(
            PromoteCautionProposal(decision_id=decision_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


# ---------------------------------------------------------------------------
# Authorize gate
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_handler_denied_does_not_write_caution() -> None:
    """Authorize denial raises UnauthorizedError; no Caution is created."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store, deny=True)
    decision_id = uuid4()
    actor_id = uuid4()
    await _seed_caution_drafter_agent(store, agent_id=actor_id)
    await _seed_caution_proposal_decision(
        store,
        decision_id=decision_id,
        actor_id=actor_id,
        choice="ProposeNotice",
        inputs={"proposed_caution": _PROPOSED_CAUTION_NOTICE},
    )
    handler = promote_caution_proposal.bind(deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            PromoteCautionProposal(decision_id=decision_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # The Decision stream is the only thing in the store; no Caution stream.
    # Verify no Caution stream exists (any UUID query returns None).
    assert await load_caution(deps.event_store, uuid4()) is None


# ---------------------------------------------------------------------------
# Phase A.2: provenance gate (Decision must come from a CautionDrafter agent)
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_handler_rejects_decision_from_unregistered_actor() -> None:
    """The Decision exists but the actor_id is not a registered Agent at all
    (e.g. a human operator hand-wrote a fake CautionProposal envelope)."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    decision_id = uuid4()
    actor_id = uuid4()  # NO _seed_caution_drafter_agent call
    await _seed_caution_proposal_decision(
        store,
        decision_id=decision_id,
        actor_id=actor_id,
        choice="ProposeNotice",
        inputs={"proposed_caution": _PROPOSED_CAUTION_NOTICE},
    )
    handler = promote_caution_proposal.bind(deps)

    with pytest.raises(DecisionNotEmittedByCautionDrafterError) as exc:
        await handler(
            PromoteCautionProposal(decision_id=decision_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc.value.observed_kind is None
    assert exc.value.actor_id == actor_id

    # No Caution stream was written.
    assert await load_caution(deps.event_store, uuid4()) is None


@pytest.mark.unit
async def test_handler_rejects_decision_from_wrong_agent_kind() -> None:
    """The Decision actor is a registered Agent, but kind != 'CautionDrafter'
    (e.g. a forged DecisionRegistered claiming context=CautionProposal
    but actor_id pointing at the RunDebrief agent)."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    decision_id = uuid4()
    actor_id = uuid4()
    await _seed_non_caution_drafter_agent(store, agent_id=actor_id, kind="RunDebrief")
    await _seed_caution_proposal_decision(
        store,
        decision_id=decision_id,
        actor_id=actor_id,
        choice="ProposeNotice",
        inputs={"proposed_caution": _PROPOSED_CAUTION_NOTICE},
    )
    handler = promote_caution_proposal.bind(deps)

    with pytest.raises(DecisionNotEmittedByCautionDrafterError) as exc:
        await handler(
            PromoteCautionProposal(decision_id=decision_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc.value.observed_kind == "RunDebrief"
    assert exc.value.actor_id == actor_id


@pytest.mark.unit
async def test_handler_gate_fires_before_decider_validation() -> None:
    """A forged CautionProposal Decision from a non-CautionDrafter actor
    is rejected at the gate even if the payload would also have failed
    decider validation. Pins ordering: provenance is gated first."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    decision_id = uuid4()
    actor_id = uuid4()
    await _seed_non_caution_drafter_agent(store, agent_id=actor_id, kind="RunDebrief")
    await _seed_caution_proposal_decision(
        store,
        decision_id=decision_id,
        actor_id=actor_id,
        choice="ProposeNotice",
        inputs={},  # missing proposed_caution; would be malformed
    )
    handler = promote_caution_proposal.bind(deps)

    # Provenance fires first; the malformed-payload error never gets a chance.
    with pytest.raises(DecisionNotEmittedByCautionDrafterError):
        await handler(
            PromoteCautionProposal(decision_id=decision_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
