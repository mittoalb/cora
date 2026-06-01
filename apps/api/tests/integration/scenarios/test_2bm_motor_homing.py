"""Motor homing at APS 2-BM.

cluster: Commissioning
archetype: routine
bc_primary: Operation
bc_touches: Caution, Equipment, Operation, Recipe

Scenario test for the shakedown rhythm: the 2 motorized Devices at
2-BM (Aerotech ABRS rotary + Sample_top_X linear) are activated and
homed without beam. One motor (Aerotech) misses its index pulse on
the first attempt, gets re-homed successfully, and earns a Caution
for the operator playbook.

See [[project_pilot_docs_design]] for the phase / file-naming
taxonomy this scenario fits into.

## Why this scenario exists

Shakedown is when motorized assets first move under power but without
beam. The lifecycle transition (Commissioned -> Active) happens here;
so do the first condition transitions (Nominal -> Degraded on a
homing failure, Degraded -> Nominal on successful re-home); so do the
first Cautions accreted against specific Assets ("this stage misses
index on cold-start, retry once").

The Procedure aggregate records the operator's command + observation
sequence (Setpoint / Action / Check entries). The Asset state changes
(`DegradeAsset`, `RestoreAsset`, `RegisterCaution`) happen via
separate slices ordered around the step entries. Asset facets
(lifecycle, condition) are inventoried into doc rows by this
scenario.

## Asset stack (the 2 motors)

The passive optical components (Oryx camera, LuAG scintillator) do
not home in the motion-control sense, so they are omitted from this
scenario. They get exercised in a separate `commissioning` scenario
when first beam touches the scintillator and the camera acquires its
first dark frames.

## What this scenario surfaces (gap-finding intent)

  - **Condition transitions are out-of-Procedure but in-narrative.**
    The operator's degrade/restore decisions are not recorded as
    Procedure step entries; they fire `DegradeAsset` / `RestoreAsset`
    slices on the Asset stream while the Procedure step log captures
    the observation that justified the call. Whether the Procedure
    should carry a `decided_to_degrade` step_kind is a watch item.
  - **Caution lifetime spans the routine.** A Caution registered
    during shakedown survives indefinitely (until superseded or
    retired) and surfaces on every future Run start via the
    `CautionLookup` snapshot. The Caution's `expires_at` is left
    `None` here so it stays on the operator's permanent banner; a
    "first-cold-start-only" expiry shape is a watch item.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.caution.aggregates.caution import (
    AssetTarget,
    CautionCategory,
    CautionSeverity,
)
from cora.caution.features.register_caution import RegisterCaution
from cora.caution.features.register_caution import bind as bind_register_caution
from cora.equipment.features.activate_asset import ActivateAsset
from cora.equipment.features.activate_asset import bind as bind_activate_asset
from cora.equipment.features.degrade_asset import DegradeAsset
from cora.equipment.features.degrade_asset import bind as bind_degrade_asset
from cora.equipment.features.restore_asset import RestoreAsset
from cora.equipment.features.restore_asset import bind as bind_restore_asset
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.operation._projections import register_operation_projections
from cora.operation.features.append_procedure_steps import (
    AppendProcedureSteps,
    ProcedureStepInput,
)
from cora.operation.features.append_procedure_steps import bind as bind_append_step
from cora.operation.features.complete_procedure import CompleteProcedure
from cora.operation.features.complete_procedure import bind as bind_complete
from cora.operation.features.register_procedure import RegisterProcedure
from cora.operation.features.register_procedure import bind as bind_register_procedure
from cora.operation.features.start_procedure import StartProcedure
from cora.operation.features.start_procedure import bind as bind_start
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_method import bind as bind_define_method
from cora.recipe.features.define_plan import DefinePlan
from cora.recipe.features.define_plan import bind as bind_define_plan
from cora.recipe.features.define_practice import DefinePractice
from cora.recipe.features.define_practice import bind as bind_define_practice
from tests.integration._helpers import (
    build_postgres_deps,
    make_pg_profile_store,
    seed_capability_postgres,
)
from tests.integration.scenarios._facility_fixture import (
    DeviceSpec,
    facility_id_prefix,
    install_aps_unit,
    operator_for,
)

_NOW = datetime(2026, 5, 17, 9, 30, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000352bb")

# Facility hierarchy mnemonic hex tags: e=enterprise, 5=site, 7=area (sector), a=unit.
# The facility-install block (actor + Argonne/APS/Unit + Devices) is consumed
# by `install_aps_unit` via `facility_id_prefix(...)`.
_ARGONNE_ENTERPRISE_ID = UUID("01900000-0000-7000-8000-000000352e01")
_APS_SITE_ID = UUID("01900000-0000-7000-8000-000000352501")
_SECTOR_2_AREA_ID = UUID("01900000-0000-7000-8000-000000352701")
_2BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000352a01")

# Capabilities (2: rotary + linear)
_CAP_ROTARY_STAGE_ID = UUID("01900000-0000-7000-8000-000000352c01")
_CAP_LINEAR_STAGE_ID = UUID("01900000-0000-7000-8000-000000352c11")

# Devices (2 motors only; camera + scintillator are passive)
_ASSET_AEROTECH_ABRS_ID = UUID("01900000-0000-7000-8000-000000352a11")
_ASSET_SAMPLE_TOP_X_ID = UUID("01900000-0000-7000-8000-000000352a21")

# Recipe ladder
_METHOD_HOMING_ID = UUID("01900000-0000-7000-8000-000000352d01")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0ec35")
_PRACTICE_HOMING_ID = UUID("01900000-0000-7000-8000-000000352d11")
_PLAN_HOMING_ID = UUID("01900000-0000-7000-8000-000000352d21")

# Procedure + lazy steps logbook
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-000000352f01")
_STEPS_LOGBOOK_ID = UUID("01900000-0000-7000-8000-000000352f11")
_STEPS_OPEN_EVENT_ID = UUID("01900000-0000-7000-8000-000000352f12")

# Caution registered against Aerotech
_CAUTION_AEROTECH_INDEX_ID = UUID("01900000-0000-7000-8000-000000352f21")


_DEVICES = (
    DeviceSpec(
        "Aerotech_ABRS_rotary", _ASSET_AEROTECH_ABRS_ID, "RotaryStage", _CAP_ROTARY_STAGE_ID
    ),
    DeviceSpec("Sample_top_X", _ASSET_SAMPLE_TOP_X_ID, "LinearStage", _CAP_LINEAR_STAGE_ID),
)


def _id_queue() -> list[UUID]:
    """Pre-allocated FixedIdGenerator queue (head-first consumption)."""
    e = uuid4
    return [
        *facility_id_prefix(
            argonne_id=_ARGONNE_ENTERPRISE_ID,
            aps_site_id=_APS_SITE_ID,
            sector_id=_SECTOR_2_AREA_ID,
            unit_id=_2BM_UNIT_ID,
            devices=_DEVICES,
        ),
        # activate_asset x 2: event_id only (no aggregate id allocated)
        e(),
        e(),
        # define_method: method_id, event_id
        _METHOD_HOMING_ID,
        e(),
        # define_practice: practice_id, event_id
        _PRACTICE_HOMING_ID,
        e(),
        # define_plan: plan_id, event_id
        _PLAN_HOMING_ID,
        e(),
        # register_procedure: procedure_id, event_id
        _PROCEDURE_ID,
        e(),
        # start_procedure: event_id
        e(),
        # append_procedure_steps (lazy open on first call): logbook_id, open_event_id
        _STEPS_LOGBOOK_ID,
        _STEPS_OPEN_EVENT_ID,
        # degrade_asset (Aerotech): event_id
        e(),
        # restore_asset (Aerotech): event_id
        e(),
        # complete_procedure: event_id
        e(),
        # register_caution (Aerotech tribal knowledge): caution_id, event_id
        _CAUTION_AEROTECH_INDEX_ID,
        e(),
    ]


def _setpoint(
    *,
    channel: str,
    target_value: float | str,
    units: str,
    role: str | None = None,
    note: str | None = None,
    sampled_at: datetime,
) -> ProcedureStepInput:
    payload: dict[str, Any] = {
        "channel": channel,
        "target_value": target_value,
        "units": units,
    }
    if role is not None:
        payload["role"] = role
    if note is not None:
        payload["note"] = note
    return ProcedureStepInput(
        event_id=uuid4(),
        step_kind="setpoint",
        payload=payload,
        sampled_at=sampled_at,
    )


def _action(
    *,
    action_name: str,
    sampled_at: datetime,
    **params: Any,
) -> ProcedureStepInput:
    return ProcedureStepInput(
        event_id=uuid4(),
        step_kind="action",
        payload={"action_name": action_name, "params": params},
        sampled_at=sampled_at,
    )


def _check(
    *,
    channel: str,
    passed: bool,
    source: str,
    sampled_at: datetime,
    actual: float | str | None = None,
    expected: float | str | None = None,
    note: str | None = None,
) -> ProcedureStepInput:
    payload: dict[str, Any] = {"channel": channel, "passed": passed, "source": source}
    if actual is not None:
        payload["actual"] = actual
    if expected is not None:
        payload["expected"] = expected
    if note is not None:
        payload["note"] = note
    return ProcedureStepInput(
        event_id=uuid4(),
        step_kind="check",
        payload=payload,
        sampled_at=sampled_at,
    )


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_operation_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


def _postgres_step_store(db_pool: asyncpg.Pool):
    """Build a PostgresStepStore for the BC-internal step writer."""
    from cora.operation.aggregates.procedure import PostgresStepStore

    return PostgresStepStore(db_pool)


@pytest.mark.integration
async def test_motor_homing_plays_out_end_to_end(
    db_pool: asyncpg.Pool,
) -> None:
    """Seed facility + 2 motors, activate them, run the homing Procedure
    with one simulated index-miss + retry on Aerotech, degrade/restore
    the Asset condition around the failure window, register a Caution
    capturing the tribal knowledge, assert the auditable record."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())

    # ----- Seed facility hierarchy: actor + Argonne -> APS -> 2-BM + 2 motor Devices -----

    await install_aps_unit(
        deps,
        profile_store=make_pg_profile_store(db_pool),
        correlation_id=_CORRELATION_ID,
        argonne_id=_ARGONNE_ENTERPRISE_ID,
        aps_site_id=_APS_SITE_ID,
        sector_id=_SECTOR_2_AREA_ID,
        unit_id=_2BM_UNIT_ID,
        devices=_DEVICES,
    )

    # ----- Equipment BC: activate both motors (Commissioned -> Active) -----

    for asset_id in (_ASSET_AEROTECH_ABRS_ID, _ASSET_SAMPLE_TOP_X_ID):
        await bind_activate_asset(deps)(
            ActivateAsset(asset_id=asset_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # ----- Recipe BC: Method + Practice + Plan for the homing routine -----

    await seed_capability_postgres(
        deps.event_store,
        _CAPABILITY_ID,
        code="cora.capability.maintenance",
        name="Maintenance",
    )

    await bind_define_method(deps)(
        DefineMethod(
            capability_id=_CAPABILITY_ID,
            name="motor_homing",
            needed_family_ids=frozenset({_CAP_ROTARY_STAGE_ID, _CAP_LINEAR_STAGE_ID}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_practice(deps)(
        DefinePractice(
            name="APS_motor_homing_practice",
            method_id=_METHOD_HOMING_ID,
            site_id=_APS_SITE_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_plan(deps)(
        DefinePlan(
            name="2BM_motor_homing_plan",
            practice_id=_PRACTICE_HOMING_ID,
            asset_ids=frozenset({_ASSET_AEROTECH_ABRS_ID, _ASSET_SAMPLE_TOP_X_ID}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Operation BC: register + start the Procedure -----

    await bind_register_procedure(deps)(
        RegisterProcedure(
            name="2-BM cold-start motor homing (Aerotech + Sample_top_X)",
            kind="motor_homing",
            target_asset_ids=frozenset({_ASSET_AEROTECH_ABRS_ID, _ASSET_SAMPLE_TOP_X_ID}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_start(deps)(
        StartProcedure(procedure_id=_PROCEDURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Procedure step entries: Aerotech first attempt (fails) -----

    t = _NOW
    await bind_append_step(deps, step_store=_postgres_step_store(db_pool))(
        AppendProcedureSteps(
            procedure_id=_PROCEDURE_ID,
            entries=(
                _setpoint(
                    channel="Aerotech_ABRS_rotary",
                    target_value="HOME",
                    units="cmd",
                    role="home_command",
                    note="cold-start, first home attempt",
                    sampled_at=t,
                ),
                _action(
                    action_name="home_motor",
                    motor="Aerotech_ABRS_rotary",
                    sampled_at=t,
                ),
                _check(
                    channel="Aerotech_ABRS_rotary.index_pulse",
                    passed=False,
                    source="encoder_index",
                    expected=1,
                    actual=0,
                    note="no index pulse detected within home-search window",
                    sampled_at=t,
                ),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Equipment BC: degrade Aerotech (operator decision on failed home) -----

    await bind_degrade_asset(deps)(
        DegradeAsset(
            asset_id=_ASSET_AEROTECH_ABRS_ID,
            reason="missed index pulse on cold-start home; one-retry policy",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Procedure step entries: Aerotech retry (succeeds) -----

    await bind_append_step(deps, step_store=_postgres_step_store(db_pool))(
        AppendProcedureSteps(
            procedure_id=_PROCEDURE_ID,
            entries=(
                _setpoint(
                    channel="Aerotech_ABRS_rotary",
                    target_value="HOME",
                    units="cmd",
                    role="home_command_retry",
                    note="retry after 5s settling period",
                    sampled_at=t,
                ),
                _action(
                    action_name="home_motor",
                    motor="Aerotech_ABRS_rotary",
                    sampled_at=t,
                ),
                _check(
                    channel="Aerotech_ABRS_rotary.index_pulse",
                    passed=True,
                    source="encoder_index",
                    expected=1,
                    actual=1,
                    sampled_at=t,
                ),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Equipment BC: restore Aerotech to Nominal -----

    await bind_restore_asset(deps)(
        RestoreAsset(
            asset_id=_ASSET_AEROTECH_ABRS_ID,
            reason="home succeeded on retry; condition cleared",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Procedure step entries: Sample_top_X (succeeds first try) -----

    await bind_append_step(deps, step_store=_postgres_step_store(db_pool))(
        AppendProcedureSteps(
            procedure_id=_PROCEDURE_ID,
            entries=(
                _setpoint(
                    channel="Sample_top_X",
                    target_value="HOME",
                    units="cmd",
                    role="home_command",
                    sampled_at=t,
                ),
                _action(
                    action_name="home_motor",
                    motor="Sample_top_X",
                    sampled_at=t,
                ),
                _check(
                    channel="Sample_top_X.home_limit_switch",
                    passed=True,
                    source="limit_switch",
                    expected="asserted",
                    actual="asserted",
                    sampled_at=t,
                ),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Operation BC: complete the Procedure -----

    await bind_complete(deps)(
        CompleteProcedure(procedure_id=_PROCEDURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Caution BC: register the tribal-knowledge Caution on Aerotech -----

    await bind_register_caution(deps)(
        RegisterCaution(
            target=AssetTarget(asset_id=_ASSET_AEROTECH_ABRS_ID),
            category=CautionCategory.WEAR,
            severity=CautionSeverity.CAUTION,
            text=(
                "Aerotech ABRS rotary stage misses index pulse on cold-start home "
                "(observed 2026-05-17 during shakedown). Affects only the first "
                "home attempt after power-cycle; subsequent homes work."
            ),
            workaround=(
                "Issue HOME command, wait 5s for settling, re-issue HOME. "
                "Verify index_pulse=1 on encoder readback before treating home "
                "as successful. Optionally pre-warm the stage by jogging "
                "+/-1deg before the first home."
            ),
            tags=frozenset({"aerotech", "home", "cold_start"}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Assert: facility hierarchy landed -----

    for asset_id in (
        _ARGONNE_ENTERPRISE_ID,
        _APS_SITE_ID,
        _2BM_UNIT_ID,
        _ASSET_AEROTECH_ABRS_ID,
        _ASSET_SAMPLE_TOP_X_ID,
    ):
        _events, version = await deps.event_store.load("Asset", asset_id)
        assert version >= 1, f"Asset {asset_id} did not land"

    # ----- Assert: Aerotech stream carries the full lifecycle + condition arc -----

    aerotech_events, _ = await deps.event_store.load("Asset", _ASSET_AEROTECH_ABRS_ID)
    aerotech_event_types = [e.event_type for e in aerotech_events]
    assert aerotech_event_types == [
        "AssetRegistered",  # genesis (Commissioned)
        "AssetFamilyAdded",  # +RotaryStage
        "AssetActivated",  # Commissioned -> Active
        "AssetDegraded",  # condition Nominal -> Degraded (after index miss)
        "AssetRestored",  # condition Degraded -> Nominal (after retry success)
    ]

    # ----- Assert: Sample_top_X carries the simpler happy-path arc -----

    sample_events, _ = await deps.event_store.load("Asset", _ASSET_SAMPLE_TOP_X_ID)
    sample_event_types = [e.event_type for e in sample_events]
    assert sample_event_types == [
        "AssetRegistered",
        "AssetFamilyAdded",
        "AssetActivated",
    ]

    # ----- Assert: Procedure stream has the expected lifecycle (4 events) -----

    procedure_events, procedure_version = await deps.event_store.load("Procedure", _PROCEDURE_ID)
    assert procedure_version == 4
    assert [e.event_type for e in procedure_events] == [
        "ProcedureRegistered",
        "ProcedureStarted",
        "ProcedureStepsLogbookOpened",
        "ProcedureCompleted",
    ]

    # ----- Assert: 9 step entries landed in the projection -----

    await _drain(db_pool)
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT step_kind FROM entries_operation_procedure_steps "
            "WHERE procedure_id = $1 ORDER BY sampled_at",
            _PROCEDURE_ID,
        )
    assert len(rows) == 9
    assert [r["step_kind"] for r in rows] == [
        "setpoint",
        "action",
        "check",  # Aerotech first attempt (failed)
        "setpoint",
        "action",
        "check",  # Aerotech retry (succeeded)
        "setpoint",
        "action",
        "check",  # Sample_top_X (succeeded first try)
    ]

    # ----- Assert: Caution registered against Aerotech -----

    caution_events, caution_version = await deps.event_store.load(
        "Caution", _CAUTION_AEROTECH_INDEX_ID
    )
    assert caution_version == 1
    assert [e.event_type for e in caution_events] == ["CautionRegistered"]
    caution_payload = caution_events[0].payload
    assert caution_payload["target"]["kind"] == "Asset"
    assert UUID(caution_payload["target"]["id"]) == _ASSET_AEROTECH_ABRS_ID
    assert caution_payload["category"] == "Wear"
    assert caution_payload["severity"] == "Caution"
