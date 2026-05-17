"""RunDebrief at APS 2-BM.

cluster: Advisories
archetype: agent-driven
bc_primary: Decision
bc_touches: Campaign, Decision, Equipment, Recipe, Run, Subject

Scenario test for CORA's first AI-agent runtime: the RunDebrief
subscriber observes the tomography scan's terminal `RunCompleted`
event, calls the LLM (stubbed via `FakeLLMAdapter`), and emits an
advisory `DecisionRegistered` with the closed 5-value choice
(NominalCompletion / DegradedCompletion / OperatorAbort /
EquipmentAbort / DataSuspect) plus an AAR narrative scaffolded into
the Decision's reasoning text.

Phase O-4 of the operations-phase canonical-acquisition chain.

See [[project_pilot_docs_design]] for the phase / file-naming
taxonomy this scenario fits into. See [[project_run_debrief_design]]
for the agent design lock.

## Why this scenario exists

CORA's agent corpus today has unit + integration + contract tier
coverage (subscriber logic, prompt construction, PG persistence
round-trip, REST/MCP surfaces), but **no scenario** exercises the
operator narrative "Run completes -> agent automatically writes
AAR". This is that scenario.

First scenario-tier exercise of:

  - `seed_run_debrief_agent(kernel)` bootstrap (registers the
    RunDebrief Agent aggregate at its pinned id + co-registers the
    Actor with kind=agent at the same id via cross-BC atomic write)
  - `RunDebriefSubscriber.apply(terminal_event)` — the side-
    effecting subscriber pathway that observes terminal Run events
    and emits Decisions
  - `FakeLLMAdapter` (the stub LLMPort used in CI; no Anthropic API
    key needed) being driven from a scenario-tier test
  - `Decision` aggregate genesis with `context=RunDebrief`,
    `decision_rule=agent:RunDebrief:v1`, `confidence_source=
    self_reported`, `actor_id=RUN_DEBRIEF_AGENT_ID`

## Why a separate scenario

Per [scenarios/README.md](../README.md) Rule 1, the agent's runtime
behavior is a separable concern from the scan it observes. The scan
(O-3) is the operator's routine; the debrief (O-4) is the agent's
routine, triggered BY the operator's Run completing. Splitting
keeps each scenario tight and lets the agent's evolution (future
debrief variants, fallback paths, ConfidenceCalibrator integration)
land in additional scenarios without bloating the scan scenario.

## Asset stack (full imaging chain, mirroring O-3)

Same as `test_2bm_tomography_scan.py`: rotary stage, sample-X,
camera, scintillator. The scan must execute end-to-end before the
agent can fire, so the full setup is replicated. Per-test template
DB isolation means we can't depend on O-3 having run; each
scenario is self-contained.

## What this scenario surfaces (gap-finding intent)

  - **The subscriber is the first side-effecting consumer in the
    projection-worker framework.** All prior subscribers were
    projections (read-side writers only); RunDebrief writes new
    events to the Decision stream. In production it runs inside
    the projection worker's loop; in this scenario we invoke
    `apply()` directly. Whether the scenario tier should grow a
    "drain subscribers" helper that mirrors `drain_projections`
    is a watch item.
  - **`FakeLLMAdapter` is a CI shortcut, not a production path.**
    The agent's real value (correctly classifying Run outcomes,
    writing useful AAR narratives) cannot be asserted with a
    canned response. The fake is for plumbing-correctness; quality
    evaluation is its own track (deferred per
    [[project_run_debrief_design]] watch items: ConfidenceCalibrator
    at N>=1000 rated). A recorded-cassette test with real
    Anthropic responses would complement this, but is itself
    deferred.
  - **LogbookMirrorPort is None today.** The subscriber accepts a
    LogbookMirrorPort that would publish the AAR to Olog / SciLog /
    SciCat; no implementor exists yet. This scenario passes None,
    matching production. When the first implementor lands, the
    scenario gains a third assertion (mirror published).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportPrivateUsage=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.agent.seed import RUN_DEBRIEF_AGENT_ID, seed_run_debrief_agent
from cora.agent.subscribers.run_debrief import (
    RunDebriefSubscriber,
    _derive_decision_id,
)
from cora.campaign.aggregates.campaign import CampaignIntent
from cora.campaign.features.add_run_to_campaign import AddRunToCampaign
from cora.campaign.features.add_run_to_campaign import bind as bind_add_run_to_campaign
from cora.decision.aggregates.decision import load_decision
from cora.equipment.features.activate_asset import ActivateAsset
from cora.equipment.features.activate_asset import bind as bind_activate_asset
from cora.infrastructure.ports import FakeLLMAdapter, FakeLLMResponse
from cora.infrastructure.ports.event_store import StoredEvent
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_method import bind as bind_define_method
from cora.recipe.features.define_plan import DefinePlan
from cora.recipe.features.define_plan import bind as bind_define_plan
from cora.recipe.features.define_practice import DefinePractice
from cora.recipe.features.define_practice import bind as bind_define_practice
from cora.recipe.features.update_method_parameters_schema import (
    UpdateMethodParametersSchema,
)
from cora.recipe.features.update_method_parameters_schema import (
    bind as bind_update_method_schema,
)
from cora.run.features.complete_run import CompleteRun
from cora.run.features.complete_run import bind as bind_complete_run
from cora.run.features.start_run import StartRun
from cora.run.features.start_run import bind as bind_start_run
from cora.subject.features.mount_subject import MountSubject
from cora.subject.features.mount_subject import bind as bind_mount_subject
from tests.integration._helpers import build_postgres_deps
from tests.integration.scenarios._beamtime_fixture import (
    BeamtimeSpec,
    beamtime_id_prefix,
    open_beamtime,
)
from tests.integration.scenarios._facility_fixture import (
    DeviceSpec,
    facility_id_prefix,
    install_aps_unit,
    operator_for,
)

_NOW = datetime(2026, 5, 17, 11, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000404bb")

# Facility hierarchy. Scenario tag: 404 (operations / RunDebrief agent).
_ARGONNE_ENTERPRISE_ID = UUID("01900000-0000-7000-8000-000000404e01")
_APS_SITE_ID = UUID("01900000-0000-7000-8000-000000404501")
_SECTOR_2_AREA_ID = UUID("01900000-0000-7000-8000-000000404701")
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000404a01")

# Capabilities (full imaging chain)
_CAP_ROTARY_STAGE_ID = UUID("01900000-0000-7000-8000-000000404c01")
_CAP_LINEAR_STAGE_ID = UUID("01900000-0000-7000-8000-000000404c11")
_CAP_CAMERA_ID = UUID("01900000-0000-7000-8000-000000404c21")
_CAP_SCINTILLATOR_ID = UUID("01900000-0000-7000-8000-000000404c31")

# Devices
_ASSET_AEROTECH_ABRS_ID = UUID("01900000-0000-7000-8000-000000404a11")
_ASSET_SAMPLE_TOP_X_ID = UUID("01900000-0000-7000-8000-000000404a21")
_ASSET_ORYX_5MP_ID = UUID("01900000-0000-7000-8000-000000404a31")
_ASSET_SCINTILLATOR_LUAG_ID = UUID("01900000-0000-7000-8000-000000404a41")

# Beamtime
_PI_ACTOR_ID = UUID("01900000-0000-7000-8000-000000404b01")
_SUBJECT_ID = UUID("01900000-0000-7000-8000-000000404b11")
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-000000404b21")

# Recipe ladder
_METHOD_TOMO_ID = UUID("01900000-0000-7000-8000-000000404d01")
_PRACTICE_TOMO_ID = UUID("01900000-0000-7000-8000-000000404d11")
_PLAN_TOMO_ID = UUID("01900000-0000-7000-8000-000000404d21")

# Run (the one the agent will debrief)
_RUN_ID = UUID("01900000-0000-7000-8000-000000404f02")

# Synthetic event_id for the terminal RunCompleted (matches the position-1
# event id assigned by start_run -> complete_run; in production the
# subscriber receives this via the projection-worker dispatch).
# We load it from the event_store after complete_run lands rather than
# guessing here.

_DEVICES = (
    DeviceSpec(
        "Aerotech_ABRS_rotary", _ASSET_AEROTECH_ABRS_ID, "RotaryStage", _CAP_ROTARY_STAGE_ID
    ),
    DeviceSpec("Sample_top_X", _ASSET_SAMPLE_TOP_X_ID, "LinearStage", _CAP_LINEAR_STAGE_ID),
    DeviceSpec("Oryx_5MP_camera", _ASSET_ORYX_5MP_ID, "Camera", _CAP_CAMERA_ID),
    DeviceSpec(
        "Scintillator_LuAG", _ASSET_SCINTILLATOR_LUAG_ID, "Scintillator", _CAP_SCINTILLATOR_ID
    ),
)

_BEAMTIME = BeamtimeSpec(
    pi_actor_id=_PI_ACTOR_ID,
    pi_actor_name="Dr. PI (Proposal 2026-1234 lead)",
    subject_id=_SUBJECT_ID,
    subject_name="porous sandstone core (Proposal 2026-1234, sample A)",
    campaign_id=_CAMPAIGN_ID,
    campaign_name="Proposal 2026-1234 beamtime",
    campaign_intent=CampaignIntent.COORDINATED,
    campaign_tags=frozenset({"proposal", "tomography", "porous_media"}),
)

_CANNED_AAR = FakeLLMResponse(
    parsed={
        "choice": "NominalCompletion",
        "confidence": 0.93,
        "reasoning": (
            "BLUF: Proposal 2026-1234 sample A scan completed nominally. "
            "Synopsis: a single-Plan tomography Run on the mounted "
            "sandstone-core Subject ran to RunCompleted in the expected "
            "window with no operator interventions. "
            "What was supposed to happen: complete the planned 1500-projection "
            "scan at 100ms exposure across 180deg sweep. "
            "What actually happened: RunCompleted; Dataset registered with "
            "NXtomo profile; Subject transitioned Mounted -> Measured cleanly. "
            "Why the difference: no difference. Nominal execution against "
            "the planned parameter envelope."
        ),
    },
    stop_reason="tool_use",
    model_id="claude-haiku-4-5",
)


def _id_queue() -> list[UUID]:
    """Pre-allocated FixedIdGenerator queue (head-first consumption).

    Note: `seed_run_debrief_agent` writes directly to the event store
    using SYSTEM_PRINCIPAL_ID and uuid4()-generated event ids; it does
    NOT consume from the FixedIdGenerator queue.
    """
    e = uuid4
    return [
        *facility_id_prefix(
            argonne_id=_ARGONNE_ENTERPRISE_ID,
            aps_site_id=_APS_SITE_ID,
            sector_id=_SECTOR_2_AREA_ID,
            unit_id=_2BM_UNIT_ID,
            devices=_DEVICES,
        ),
        e(),
        e(),
        e(),
        e(),  # activate_asset x 4
        *beamtime_id_prefix(spec=_BEAMTIME),
        e(),  # mount_subject
        _METHOD_TOMO_ID,
        e(),  # define_method
        e(),  # update_method_parameters_schema
        _PRACTICE_TOMO_ID,
        e(),  # define_practice
        _PLAN_TOMO_ID,
        e(),  # define_plan
        _RUN_ID,
        e(),  # start_run
        e(),
        e(),  # add_run_to_campaign (CampaignRunAdded + RunCampaignAssigned)
        e(),  # complete_run
    ]


@pytest.mark.integration
async def test_run_debrief_agent_fires_on_terminal_run(
    db_pool: asyncpg.Pool,
) -> None:
    """Replicate the tomography-scan setup (O-3 ceremony in compact
    form), let the Run reach the terminal `RunCompleted` state, seed
    the RunDebrief Agent, invoke the subscriber against the terminal
    event with a canned LLM response, assert the advisory
    `DecisionRegistered` lands with the expected RunDebrief shape."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())

    # ----- O-1 + O-2 + O-3 compact setup (facility + beamtime + scan to terminal) -----

    await install_aps_unit(
        deps,
        correlation_id=_CORRELATION_ID,
        argonne_id=_ARGONNE_ENTERPRISE_ID,
        aps_site_id=_APS_SITE_ID,
        sector_id=_SECTOR_2_AREA_ID,
        unit_id=_2BM_UNIT_ID,
        devices=_DEVICES,
        unit_name="2-BM",
        sector_name="Sector 2",
    )

    for asset_id in (
        _ASSET_AEROTECH_ABRS_ID,
        _ASSET_SAMPLE_TOP_X_ID,
        _ASSET_ORYX_5MP_ID,
        _ASSET_SCINTILLATOR_LUAG_ID,
    ):
        await bind_activate_asset(deps)(
            ActivateAsset(asset_id=asset_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    await open_beamtime(
        deps,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        spec=_BEAMTIME,
    )

    await bind_mount_subject(deps)(
        MountSubject(
            subject_id=_SUBJECT_ID,
            asset_id=_ASSET_AEROTECH_ABRS_ID,
            reason="first proposal scan; sandstone core sample A on kinematic tip",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await bind_define_method(deps)(
        DefineMethod(
            name="tomography",
            needed_capabilities=frozenset(
                {
                    _CAP_ROTARY_STAGE_ID,
                    _CAP_LINEAR_STAGE_ID,
                    _CAP_CAMERA_ID,
                    _CAP_SCINTILLATOR_ID,
                }
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_update_method_schema(deps)(
        UpdateMethodParametersSchema(
            method_id=_METHOD_TOMO_ID,
            parameters_schema={
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "exposure_ms": {"type": "integer", "minimum": 1},
                    "n_projections": {"type": "integer", "minimum": 1},
                    "angle_range_deg": {"type": "number", "minimum": 1, "maximum": 360},
                },
                "required": ["exposure_ms", "n_projections", "angle_range_deg"],
            },
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_practice(deps)(
        DefinePractice(
            name="2BM_tomography_practice",
            method_id=_METHOD_TOMO_ID,
            site_id=_APS_SITE_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_plan(deps)(
        DefinePlan(
            name="2BM_porous_media_tomography_plan",
            practice_id=_PRACTICE_TOMO_ID,
            asset_ids=frozenset(
                {
                    _ASSET_AEROTECH_ABRS_ID,
                    _ASSET_SAMPLE_TOP_X_ID,
                    _ASSET_ORYX_5MP_ID,
                    _ASSET_SCINTILLATOR_LUAG_ID,
                }
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await bind_start_run(deps)(
        StartRun(
            name="Proposal 2026-1234 sample A tomography",
            plan_id=_PLAN_TOMO_ID,
            subject_id=_SUBJECT_ID,
            override_parameters={
                "exposure_ms": 100,
                "n_projections": 1500,
                "angle_range_deg": 180.0,
            },
            triggered_by="operator-manual; first scan of beamtime",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_add_run_to_campaign(deps)(
        AddRunToCampaign(campaign_id=_CAMPAIGN_ID, run_id=_RUN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_complete_run(deps)(
        CompleteRun(run_id=_RUN_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- O-4 specific: seed RunDebrief Agent + invoke subscriber on terminal -----

    # Bootstrap the agent (idempotent on re-invocation; uses SYSTEM_PRINCIPAL_ID
    # internally so the seed events bypass the FixedIdGenerator queue).
    await seed_run_debrief_agent(deps)

    # Load the terminal RunCompleted event from the Run stream.
    run_events, _run_version = await deps.event_store.load("Run", _RUN_ID)
    terminal_storedevents = [e for e in run_events if e.event_type == "RunCompleted"]
    assert len(terminal_storedevents) == 1, "expected exactly one RunCompleted on the Run stream"
    terminal_event = terminal_storedevents[0]
    # The agent subscriber receives StoredEvent shape per the projection-worker
    # dispatch contract; loaded events from the event_store already are
    # StoredEvent instances.
    assert isinstance(terminal_event, StoredEvent)

    # Build the subscriber with a canned LLM response. LogbookMirrorPort is
    # None today (no implementor; see [[project_run_debrief_design]]).
    llm = FakeLLMAdapter(responses=[_CANNED_AAR])
    subscriber = RunDebriefSubscriber(
        event_store=deps.event_store,
        llm=llm,
        logbook_mirror=None,
    )

    # Fire the subscriber. In production the projection worker dispatches
    # this from its loop; in scenarios we invoke apply() directly.
    await subscriber.apply(terminal_event, conn=None)

    # ----- Assert: Decision landed with expected RunDebrief shape -----

    decision_id = _derive_decision_id(terminal_event.event_id)
    decision = await load_decision(deps.event_store, decision_id)
    assert decision is not None
    assert decision.context.value == "RunDebrief"
    assert decision.choice.value == "NominalCompletion"
    assert decision.actor_id == RUN_DEBRIEF_AGENT_ID

    # ----- Assert: LLM was called exactly once with the run_id in context -----

    assert len(llm.received) == 1
    prompt_text = llm.received[0].user_message.text
    assert str(_RUN_ID) in prompt_text, "subscriber prompt must reference the Run being debriefed"

    # ----- Assert: agent's Decision stream is at version 1 (single-event genesis) -----

    decision_events, decision_version = await deps.event_store.load("Decision", decision_id)
    assert decision_version == 1
    assert [e.event_type for e in decision_events] == ["DecisionRegistered"]
    decision_payload = decision_events[0].payload
    assert decision_payload["context"] == "RunDebrief"
    assert decision_payload["choice"] == "NominalCompletion"
    assert decision_payload["decision_rule"] == "agent:RunDebrief:v1"
    assert decision_payload["confidence_source"] == "self_reported"
    assert UUID(decision_payload["actor_id"]) == RUN_DEBRIEF_AGENT_ID
