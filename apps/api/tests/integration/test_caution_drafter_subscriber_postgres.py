"""End-to-end PG integration for CautionDrafter (Phase 8f-c iter 3 follow-up).

Walks the full cross-BC seam on real Postgres:

  1. Seed CautionDrafter Agent + Actor (bootstrap).
  2. Seed a Plan (subscriber loads Plan for asset_ids).
  3. Seed a Run.
  4. Invoke the subscriber against a terminal Run event with a
     canned LLM `ProposeCaution` response.
  5. Verify a `DecisionRegistered(context="CautionProposal")` landed
     on the Decision stream with the proposed_caution payload.
  6. Invoke `promote_caution_proposal` against the Decision.
  7. Verify a real Caution was registered in Caution BC via the
     cross-BC write (the promote handler composes `CautionRegistered`
     events directly via `EventStore.append_streams`, mirroring
     `define_agent`'s pattern; no sibling-features import).
  8. Sanity-check at-most-once on the subscriber (second apply is a
     no-op via ConcurrencyError on the deterministic decision_id).

Uses `FakeLLMAdapter` for the LLM call (no Anthropic API key needed
in CI). Real-Anthropic recorded-cassette test remains a watch item.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingParameterType=false, reportPrivateUsage=false, reportUnknownParameterType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.agent.features import promote_caution_proposal
from cora.agent.features.promote_caution_proposal import PromoteCautionProposal
from cora.agent.seed_caution_drafter import (
    CAUTION_DRAFTER_AGENT_ID,
    seed_caution_drafter_agent,
)
from cora.agent.subscribers.caution_drafter import (
    CautionDrafterSubscriber,
    _derive_decision_id,
)
from cora.caution.aggregates.caution import (
    CautionCategory,
    CautionSeverity,
    CautionStatus,
    load_caution,
)
from cora.decision.aggregates.decision import load_decision
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.ports import FakeLLMAdapter, FakeLLMResponse
from cora.infrastructure.ports.event_store import StoredEvent
from cora.recipe.aggregates.plan import PlanDefined
from cora.recipe.aggregates.plan import event_type_name as plan_event_type_name
from cora.recipe.aggregates.plan import to_payload as plan_to_payload
from cora.run.aggregates.run import RunStarted
from cora.run.aggregates.run import event_type_name as run_event_type_name
from cora.run.aggregates.run import to_payload as run_to_payload
from cora.run.aggregates.run.events import RunAborted
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 17, 14, 0, 0, tzinfo=UTC)
_LATER = datetime(2026, 5, 17, 14, 47, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000099b01")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000009900b")

_ASSET_ID = UUID("01900000-0000-7000-8000-000000000bbb")
_PRACTICE_ID = UUID("01900000-0000-7000-8000-000000000bbc")
_METHOD_ID = UUID("01900000-0000-7000-8000-000000000bbd")


async def _seed_plan(deps, plan_id: UUID) -> None:
    plan = PlanDefined(
        plan_id=plan_id,
        name="PG Integration Test Plan",
        practice_id=_PRACTICE_ID,
        asset_ids=[_ASSET_ID],
        method_id=_METHOD_ID,
        method_needed_capabilities_snapshot=[],
        asset_capabilities_snapshot={_ASSET_ID: []},
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=plan_event_type_name(plan),
        payload=plan_to_payload(plan),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="DefinePlan",
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        principal_id=_PRINCIPAL_ID,
    )
    await deps.event_store.append(
        stream_type="Plan",
        stream_id=plan_id,
        expected_version=0,
        events=[new_event],
    )


async def _seed_run(deps, run_id: UUID, plan_id: UUID) -> None:
    started = RunStarted(
        run_id=run_id,
        name="PG Integration Test Run",
        plan_id=plan_id,
        subject_id=None,
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=run_event_type_name(started),
        payload=run_to_payload(started),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="StartRun",
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        principal_id=_PRINCIPAL_ID,
    )
    await deps.event_store.append(
        stream_type="Run",
        stream_id=run_id,
        expected_version=0,
        events=[new_event],
    )


def _terminal_aborted_event(run_id: UUID) -> StoredEvent:
    domain = RunAborted(
        run_id=run_id,
        reason="rotary stage encoder offline; interlock fired",
        occurred_at=_LATER,
    )
    return StoredEvent(
        position=1,
        event_id=UUID("01900000-0000-7000-8000-00000000fb01"),
        stream_type="Run",
        stream_id=run_id,
        version=2,
        event_type="RunAborted",
        schema_version=1,
        payload=run_to_payload(domain),
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        occurred_at=_LATER,
        recorded_at=_LATER,
    )


def _canned_propose_caution_response() -> FakeLLMResponse:
    return FakeLLMResponse(
        parsed={
            "choice": "ProposeCaution",
            "confidence": 0.74,
            "confidence_band": "medium",
            "reasoning": (
                "PG integration test: terminal RunAborted with hardware "
                "vocabulary in the reason field indicates a real operator-"
                "actionable pattern; encoder went offline after extended "
                "rotation, suggesting heat-related drift."
            ),
            "proposed_caution": {
                "target_kind": "Asset",
                "target_id": str(_ASSET_ID),
                "category": "Wear",
                "severity": "Caution",
                "title": "Encoder drift after extended rotation",
                "body": (
                    "Re-home the rotary stage encoder every 10 minutes of "
                    "continuous rotation; drift accumulates and triggers "
                    "interlock at ~12 minutes."
                ),
                "tags": ["encoder", "rotary-stage", "rotation"],
            },
        },
        stop_reason="tool_use",
        model_id="claude-sonnet-4-6",
    )


@pytest.mark.integration
async def test_subscriber_writes_caution_proposal_decision_end_to_end(
    db_pool: asyncpg.Pool,
) -> None:
    """Step 1-5 of the end-to-end walk: subscriber emits the Decision."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(10)])
    await seed_caution_drafter_agent(deps)
    # Idempotent on real PG.
    await seed_caution_drafter_agent(deps)

    plan_id = uuid4()
    run_id = uuid4()
    await _seed_plan(deps, plan_id)
    await _seed_run(deps, run_id, plan_id)

    llm = FakeLLMAdapter(responses=[_canned_propose_caution_response()])
    subscriber = CautionDrafterSubscriber(
        event_store=deps.event_store,
        llm=llm,
        caution_lookup=deps.caution_lookup,
    )
    event = _terminal_aborted_event(run_id)

    await subscriber.apply(event, conn=None)

    decision_id = _derive_decision_id(event.event_id)
    decision = await load_decision(deps.event_store, decision_id)
    assert decision is not None
    assert decision.context.value == "CautionProposal"
    assert decision.choice.value == "ProposeCaution"
    assert decision.actor_id == CAUTION_DRAFTER_AGENT_ID
    assert decision.decision_inputs is not None
    proposed = decision.decision_inputs["proposed_caution"]
    assert proposed["target_id"] == str(_ASSET_ID)
    assert proposed["category"] == "Wear"
    assert proposed["severity"] == "Caution"
    # informed_by_decision_id always None at v1 (DecisionLookup deferred).
    assert decision.decision_inputs["informed_by_decision_id"] is None

    # LLM call captured the candidate target.
    assert len(llm.received) == 1
    assert str(_ASSET_ID) in llm.received[0].user_message.text


@pytest.mark.integration
async def test_end_to_end_cross_bc_promotion_registers_real_caution(
    db_pool: asyncpg.Pool,
) -> None:
    """Full Stage 0 design proof: subscriber emits Decision, operator
    promotes via Agent BC's slice, Caution lands in Caution BC's stream."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(10)])
    await seed_caution_drafter_agent(deps)

    plan_id = uuid4()
    run_id = uuid4()
    await _seed_plan(deps, plan_id)
    await _seed_run(deps, run_id, plan_id)

    # Step 1: subscriber emits the CautionProposal Decision.
    llm = FakeLLMAdapter(responses=[_canned_propose_caution_response()])
    subscriber = CautionDrafterSubscriber(
        event_store=deps.event_store,
        llm=llm,
        caution_lookup=deps.caution_lookup,
    )
    event = _terminal_aborted_event(run_id)
    await subscriber.apply(event, conn=None)
    decision_id = _derive_decision_id(event.event_id)

    # Step 2: operator promotes the Decision via Agent BC's cross-BC slice.
    handler = promote_caution_proposal.bind(deps)
    caution_id = await handler(
        PromoteCautionProposal(decision_id=decision_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Step 3: a real Caution exists in Caution BC's stream with the
    # proposed payload (Pattern C cross-BC slice delegation worked).
    caution = await load_caution(deps.event_store, caution_id)
    assert caution is not None
    assert caution.status == CautionStatus.ACTIVE
    assert caution.severity == CautionSeverity.CAUTION
    assert caution.category == CautionCategory.WEAR
    assert caution.text.value.startswith("Encoder drift")
    assert caution.workaround.value.startswith("Re-home")


@pytest.mark.integration
async def test_subscriber_is_at_most_once_on_real_pg(
    db_pool: asyncpg.Pool,
) -> None:
    """Second apply with the same terminal event is a no-op on real PG
    (ConcurrencyError on the deterministic decision_id is caught)."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(10)])
    await seed_caution_drafter_agent(deps)

    plan_id = uuid4()
    run_id = uuid4()
    await _seed_plan(deps, plan_id)
    await _seed_run(deps, run_id, plan_id)

    llm = FakeLLMAdapter(
        responses=[
            _canned_propose_caution_response(),
            _canned_propose_caution_response(),
        ]
    )
    subscriber = CautionDrafterSubscriber(
        event_store=deps.event_store,
        llm=llm,
        caution_lookup=deps.caution_lookup,
    )
    event = _terminal_aborted_event(run_id)

    await subscriber.apply(event, conn=None)
    await subscriber.apply(event, conn=None)

    decision_id = _derive_decision_id(event.event_id)
    events_list, version = await deps.event_store.load("Decision", decision_id)
    assert version == 1
    assert len(events_list) == 1
