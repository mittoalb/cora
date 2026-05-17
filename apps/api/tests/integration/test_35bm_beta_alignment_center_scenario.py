"""Phase: beta. Routine: center alignment at APS 35-BM.

Scenario test for the rotation-axis "center" alignment routine at 35-BM
micro-CT, as performed by operators today at mechanically-similar 2-BM
via the `xray-imaging/adjust` CLI. Composes the full Equipment + Recipe
+ Operation BC stack end-to-end for one real beamline routine.

See [[project_scenario_taxonomy]] for the phase / file-naming taxonomy
this scenario fits into.

## Why this test exists

The value is not a green CI light; it is **gap-surfacing**: do the
synthetic-BC-shape decisions hold up when expressed against a real
operator workflow? Each gap surfaced becomes a watch item or design
memo addition, not a fix in this file.

## Domain shape (synthesized from APS tomoscan + 2bm-docs)

A "rotation-axis alignment" is iterative:

  1. Mount the calibration sphere on the kinematic tip.
  2. Rotate to 0°, acquire alignment image, note sphere centroid x.
  3. Rotate to 180°, acquire alignment image, note sphere centroid x.
  4. Compute offset = (centroid_at_180 - centroid_at_0) / 2.
  5. If |offset| > tolerance: adjust Sample_top_X by -offset, goto 2.
  6. Else: write the calibrated rotation-axis pixel position to the
     `RotationCenter` PV. Done.

Convergence typically takes 2-3 iterations starting from a few-pixel
misalignment. The "Check" outcome is the operator's judgment that
sphere centroids match within tolerance; in production this is a
visual call (live tomostream centroid overlay) or an off-line
reconstruction-quality metric (`tomopy.find_center_vo`). Either way,
the success criterion lives outside CORA — CORA records the Check
the operator made + the evidence they cite.

## Asset stack (minimal-but-faithful)

Four target Assets cover the load-bearing instruments:

  - Aerotech ABRS rotary stage (the rotation axis)
  - Sample_top_X linear stage (the X-correction motor; a Kohzu CYAT-070)
  - FLIR Oryx 5MP camera (the alignment-frame detector)
  - LuAG scintillator (converts X-rays to visible for the camera)

Each gets one Capability defined day-one. The hexapod, sample_y,
phantom, and beamline-envelope Assets are deliberately omitted from
the Procedure's target_asset_ids — they're upstream / supporting,
not directly manipulated during the center routine.

## What this test surfaces (gap-finding intent)

See `docs/deployments/35-bm/procedures.md` (the operator-facing
companion) for the gaps documented in domain terms. The most consequential surfaces are:

  - **Iteration loop has no first-class shape**: alignment IS iterative
    (rotate → check → adjust → re-rotate); we encode iteration via
    repeated step entries with an `iteration` payload key. Whether
    iteration deserves a dedicated step_kind ("loop_marker") is a
    watch item.
  - **External-tool delegation**: the convergence Check requires
    off-line reconstruction. We model that via `payload.source =
    "operator_visual" | "tomopy_find_center_vo" | "live_tomostream"`
    on Check entries; whether that source-of-truth needs structuring
    is a watch item.
  - **Two-namesake-motor problem** (Tomo@0deg vs Tomo@180deg, same
    physical Asset, two semantic roles): we use the canonical
    `Sample_top_X` name with a `role` payload key on the Setpoint;
    whether AssetPort needs context-dependent identity is a watch
    item.
  - **No discrete success boolean exists in PVs**: the final Check is
    operator judgment + off-line metric. We capture both via the
    polymorphic JSON payload, validating the Path-C trichotomy
    decision from 10c-b.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.access.features.register_actor import RegisterActor
from cora.access.features.register_actor import bind as bind_register_actor
from cora.equipment.aggregates.asset import AssetLevel
from cora.equipment.features.add_asset_capability import (
    AddAssetCapability,
)
from cora.equipment.features.add_asset_capability import (
    bind as bind_add_capability,
)
from cora.equipment.features.define_capability import (
    DefineCapability,
)
from cora.equipment.features.define_capability import (
    bind as bind_define_capability,
)
from cora.equipment.features.register_asset import (
    RegisterAsset,
)
from cora.equipment.features.register_asset import (
    bind as bind_register_asset,
)
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.operation._projections import register_operation_projections
from cora.operation.aggregates.procedure import ProcedureStatus
from cora.operation.features.append_procedure_step import (
    AppendProcedureSteps,
    ProcedureStepInput,
)
from cora.operation.features.append_procedure_step import (
    bind as bind_append_step,
)
from cora.operation.features.complete_procedure import (
    CompleteProcedure,
)
from cora.operation.features.complete_procedure import (
    bind as bind_complete,
)
from cora.operation.features.list_procedures import (
    ListProcedures,
)
from cora.operation.features.list_procedures import (
    bind as bind_list,
)
from cora.operation.features.register_procedure import (
    RegisterProcedure,
)
from cora.operation.features.register_procedure import (
    bind as bind_register_procedure,
)
from cora.operation.features.start_procedure import (
    StartProcedure,
)
from cora.operation.features.start_procedure import (
    bind as bind_start,
)
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_method import bind as bind_define_method
from cora.recipe.features.define_plan import DefinePlan
from cora.recipe.features.define_plan import bind as bind_define_plan
from cora.recipe.features.define_practice import (
    DefinePractice,
)
from cora.recipe.features.define_practice import (
    bind as bind_define_practice,
)
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 15, 14, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000003500")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000035bb")

# Pre-allocated id queue. Order matters (FixedIdGenerator consumes head-first).
# Each block annotates which command consumes which IDs.

# Access BC: the operator Actor registered first; its id IS _PRINCIPAL_ID so
# subsequent calls reference a real Actor instead of a placeholder UUID.
_ACTOR_OPERATOR_ID = _PRINCIPAL_ID

# Asset hierarchy: Argonne (Enterprise) → APS (Site) → 35-BM (Unit). Devices
# below hang off _35BM_UNIT_ID. Practice's site_id references _APS_SITE_ID.
_ARGONNE_ENTERPRISE_ID = UUID("01900000-0000-7000-8000-000000350e01")
_APS_SITE_ID = UUID("01900000-0000-7000-8000-000000350501")
_35BM_UNIT_ID = UUID("01900000-0000-7000-8000-000000350a01")

# Capability ids (4 caps x 2 ids/define = 8)
_CAP_ROTARY_STAGE_ID = UUID("01900000-0000-7000-8000-000000035c01")
_CAP_LINEAR_STAGE_ID = UUID("01900000-0000-7000-8000-000000035c11")
_CAP_CAMERA_ID = UUID("01900000-0000-7000-8000-000000035c21")
_CAP_SCINTILLATOR_ID = UUID("01900000-0000-7000-8000-000000035c31")

# Asset ids (4 assets x {2 register + 1 addcap} = 12 ids; we name only the asset ids)
_ASSET_AEROTECH_ABRS_ID = UUID("01900000-0000-7000-8000-000000035a01")
_ASSET_SAMPLE_TOP_X_ID = UUID("01900000-0000-7000-8000-000000035a11")
_ASSET_ORYX_5MP_ID = UUID("01900000-0000-7000-8000-000000035a21")
_ASSET_SCINTILLATOR_LUAG_ID = UUID("01900000-0000-7000-8000-000000035a31")

# Recipe ids
_METHOD_ID = UUID("01900000-0000-7000-8000-000000035d01")
_PRACTICE_ID = UUID("01900000-0000-7000-8000-000000035d11")
_PLAN_ID = UUID("01900000-0000-7000-8000-000000035d21")

# Procedure id
_PROCEDURE_ID = UUID("01900000-0000-7000-8000-000000035e01")

# Steps logbook + open envelope
_STEPS_LOGBOOK_ID = UUID("01900000-0000-7000-8000-000000035f01")
_STEPS_OPEN_EVENT_ID = UUID("01900000-0000-7000-8000-000000035f02")


def _id_queue() -> list[UUID]:
    """Build the FixedIdGenerator queue. Anonymous event ids are uuid4()."""
    e = uuid4  # alias for brevity
    return [
        # register_actor (operator, principal): actor_id, event_id
        _ACTOR_OPERATOR_ID,
        e(),
        # register_asset Argonne (Enterprise): asset_id, event_id
        _ARGONNE_ENTERPRISE_ID,
        e(),
        # register_asset APS (Site, parent=Argonne): asset_id, event_id
        _APS_SITE_ID,
        e(),
        # register_asset 35-BM (Unit, parent=APS): asset_id, event_id
        _35BM_UNIT_ID,
        e(),
        # define_capability x 4: cap_id, event_id
        _CAP_ROTARY_STAGE_ID,
        e(),
        _CAP_LINEAR_STAGE_ID,
        e(),
        _CAP_CAMERA_ID,
        e(),
        _CAP_SCINTILLATOR_ID,
        e(),
        # register_asset x 4: asset_id, register_event_id
        # add_asset_capability x 4: addcap_event_id
        _ASSET_AEROTECH_ABRS_ID,
        e(),
        e(),  # add_capability event
        _ASSET_SAMPLE_TOP_X_ID,
        e(),
        e(),
        _ASSET_ORYX_5MP_ID,
        e(),
        e(),
        _ASSET_SCINTILLATOR_LUAG_ID,
        e(),
        e(),
        # define_method: method_id, event_id
        _METHOD_ID,
        e(),
        # define_practice: practice_id, event_id
        _PRACTICE_ID,
        e(),
        # define_plan: plan_id, event_id
        _PLAN_ID,
        e(),
        # register_procedure: procedure_id, event_id
        _PROCEDURE_ID,
        e(),
        # start_procedure: event_id
        e(),
        # append_procedure_step (lazy-open on first call): logbook_id, open_event_id
        _STEPS_LOGBOOK_ID,
        _STEPS_OPEN_EVENT_ID,
        # complete_procedure: event_id
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
    """Build a Setpoint step input. `role` carries context-dependent
    semantics (e.g., Tomo@0deg vs Tomo@180deg for the same physical
    Sample_top_X motor). `note` is operator's free-text per-step audit."""
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
    """Build an Action step input. `params` are kind-specific."""
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
    actual: float | None = None,
    expected: float | None = None,
    tolerance: float | None = None,
    source: str = "operator_visual",
    sampled_at: datetime,
    **evidence: Any,
) -> ProcedureStepInput:
    """Build a Check step input. `source` distinguishes operator-visual
    judgment from off-line metrics (e.g., tomopy.find_center_vo)."""
    payload: dict[str, Any] = {
        "channel": channel,
        "passed": passed,
        "source": source,
    }
    if actual is not None:
        payload["actual"] = actual
    if expected is not None:
        payload["expected"] = expected
    if tolerance is not None:
        payload["tolerance"] = tolerance
    if evidence:
        payload["evidence"] = evidence
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


@pytest.mark.integration
async def test_center_alignment_plays_out_end_to_end(
    db_pool: asyncpg.Pool,
) -> None:
    """Seed Equipment + Recipe + Operation, run the iterative 0°/180°
    convergence loop, finalize with RotationCenter setpoint, drain the
    projection, assert the operator-readable record is correct.
    """
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())

    # ----- Seed Access BC: register the operator Actor (id = _PRINCIPAL_ID) -----

    await bind_register_actor(deps)(
        RegisterActor(name="35-BM Operator"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Seed Equipment BC (facility hierarchy): Argonne → APS → 35-BM Unit -----

    await bind_register_asset(deps)(
        RegisterAsset(name="Argonne", level=AssetLevel.ENTERPRISE, parent_id=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_register_asset(deps)(
        RegisterAsset(name="APS", level=AssetLevel.SITE, parent_id=_ARGONNE_ENTERPRISE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_register_asset(deps)(
        RegisterAsset(name="35-BM", level=AssetLevel.UNIT, parent_id=_APS_SITE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Seed Equipment BC: 4 Capabilities + 4 Devices + 4 capability links -----

    for cap_name in ("RotaryStage", "LinearStage", "Camera", "Scintillator"):
        await bind_define_capability(deps)(
            DefineCapability(name=cap_name),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    asset_specs = [
        ("Aerotech_ABRS_rotary", _ASSET_AEROTECH_ABRS_ID, _CAP_ROTARY_STAGE_ID),
        ("Sample_top_X", _ASSET_SAMPLE_TOP_X_ID, _CAP_LINEAR_STAGE_ID),
        ("Oryx_5MP_camera", _ASSET_ORYX_5MP_ID, _CAP_CAMERA_ID),
        ("Scintillator_LuAG", _ASSET_SCINTILLATOR_LUAG_ID, _CAP_SCINTILLATOR_ID),
    ]
    for asset_name, asset_id, cap_id in asset_specs:
        await bind_register_asset(deps)(
            RegisterAsset(name=asset_name, level=AssetLevel.DEVICE, parent_id=_35BM_UNIT_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        await bind_add_capability(deps)(
            AddAssetCapability(asset_id=asset_id, capability_id=cap_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # ----- Seed Recipe BC: Method + Practice + Plan describing the alignment recipe -----

    await bind_define_method(deps)(
        DefineMethod(
            name="center_alignment",
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
    await bind_define_practice(deps)(
        DefinePractice(name="35BM_alignment_practice", method_id=_METHOD_ID, site_id=_APS_SITE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_define_plan(deps)(
        DefinePlan(
            name="35BM_center_routine_plan",
            practice_id=_PRACTICE_ID,
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

    # ----- Operation BC: register + start the Procedure -----

    await bind_register_procedure(deps)(
        RegisterProcedure(
            name="35-BM rotation-axis alignment (vessel-A bakeout pre-scan)",
            kind="center_alignment",
            target_asset_ids=frozenset(
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
    await bind_start(deps)(
        StartProcedure(procedure_id=_PROCEDURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Append the alignment step sequence (one full convergence) -----

    # Step timestamps walk forward by 1 second each, like real operator gestures.
    def t(seconds: int) -> datetime:
        return datetime(2026, 5, 15, 14, 0, seconds, tzinfo=UTC)

    # Iteration 1: large initial offset. Convergence fails.
    iter1_steps = (
        _setpoint(
            channel="Tomo_Rot",
            target_value=0.0,
            units="deg",
            note="initial 0deg reference; iteration=1",
            sampled_at=t(1),
        ),
        _action(
            action_name="acquire_alignment_frame",
            exposure_time=0.05,
            frame_type="Projection",
            hdf5_location="/exchange/data/align_iter1_0deg.h5",
            sampled_at=t(2),
        ),
        _check(
            channel="sphere_centroid_x_px",
            passed=True,
            actual=1024.0,
            expected=1024.0,
            tolerance=5.0,
            source="live_tomostream_centroid",
            iteration=1,
            sampled_at=t(3),
        ),
        _setpoint(
            channel="Tomo_Rot",
            target_value=180.0,
            units="deg",
            note="180deg counterpart; iteration=1",
            sampled_at=t(4),
        ),
        _action(
            action_name="acquire_alignment_frame",
            exposure_time=0.05,
            frame_type="Projection",
            hdf5_location="/exchange/data/align_iter1_180deg.h5",
            sampled_at=t(5),
        ),
        _check(
            channel="sphere_centroid_x_px",
            passed=False,
            actual=1031.0,
            expected=1024.0,
            tolerance=1.0,
            source="live_tomostream_centroid",
            iteration=1,
            offset_px=7.0,
            sampled_at=t(6),
        ),
        # Correction: offset_px / 2 = 3.5 px. Pixel size ~1 um per px (typical 5x lens),
        # so correction is ~3.5 um in motor units. Operator chooses the sign by convention.
        _setpoint(
            channel="Sample_top_X",
            target_value=-3.5,
            units="um",
            role="Tomo@180deg",
            note="X-correction for iter 1 offset; convention: -offset_px / 2",
            sampled_at=t(7),
        ),
    )

    # Iteration 2: converges within tolerance.
    iter2_steps = (
        _setpoint(
            channel="Tomo_Rot",
            target_value=0.0,
            units="deg",
            note="post-correction 0deg reference; iteration=2",
            sampled_at=t(8),
        ),
        _action(
            action_name="acquire_alignment_frame",
            exposure_time=0.05,
            frame_type="Projection",
            hdf5_location="/exchange/data/align_iter2_0deg.h5",
            sampled_at=t(9),
        ),
        _setpoint(
            channel="Tomo_Rot",
            target_value=180.0,
            units="deg",
            note="180deg post-correction; iteration=2",
            sampled_at=t(10),
        ),
        _action(
            action_name="acquire_alignment_frame",
            exposure_time=0.05,
            frame_type="Projection",
            hdf5_location="/exchange/data/align_iter2_180deg.h5",
            sampled_at=t(11),
        ),
        _check(
            channel="sphere_centroid_x_px",
            passed=True,
            actual=1024.5,
            expected=1024.0,
            tolerance=1.0,
            source="live_tomostream_centroid",
            iteration=2,
            offset_px=0.5,
            sampled_at=t(12),
        ),
    )

    # Finalize: write the calibrated rotation-axis pixel position to the PV
    # consumed by downstream science scans.
    finalize_step = _setpoint(
        channel="RotationCenter",
        target_value=1024.5,
        units="px",
        note="calibrated rotation-axis pixel position for 35-BM micro-CT",
        sampled_at=t(13),
    )

    all_steps = iter1_steps + iter2_steps + (finalize_step,)
    assert len(all_steps) == 13, "expected 13 steps for one full convergence"

    # Append all steps in one batch (operator-realistic; matches how DAQ
    # adapters batch and matches the AppendProcedureSteps batch shape).
    count = await bind_append_step(deps, step_store=_postgres_step_store(db_pool))(
        AppendProcedureSteps(procedure_id=_PROCEDURE_ID, entries=all_steps),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert count == 13

    # ----- Complete the Procedure -----

    await bind_complete(deps)(
        CompleteProcedure(procedure_id=_PROCEDURE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # ----- Assert the Procedure stream tells the right lifecycle story -----

    events, version = await deps.event_store.load("Procedure", _PROCEDURE_ID)
    # Expected event sequence: Registered, Started, StepsLogbookOpened, Completed.
    assert version == 4, f"expected 4 events on Procedure stream, got {version}"
    event_types = [e.event_type for e in events]
    assert event_types == [
        "ProcedureRegistered",
        "ProcedureStarted",
        "ProcedureStepsLogbookOpened",
        "ProcedureCompleted",
    ]

    # ----- Assert the per-step logbook table has all 13 entries with the right kinds -----

    step_rows = await _read_steps(db_pool, _PROCEDURE_ID)
    assert len(step_rows) == 13
    kinds_in_order = [r["step_kind"] for r in step_rows]
    expected_kinds = [
        # iter 1
        "setpoint",
        "action",
        "check",
        "setpoint",
        "action",
        "check",
        "setpoint",
        # iter 2
        "setpoint",
        "action",
        "setpoint",
        "action",
        "check",
        # finalize
        "setpoint",
    ]
    assert kinds_in_order == expected_kinds

    # The final setpoint records the calibrated rotation-axis pixel position --
    # the artifact a downstream science scan will read.
    final_setpoint_payload = json.loads(step_rows[-1]["payload"])
    assert final_setpoint_payload["channel"] == "RotationCenter"
    assert final_setpoint_payload["target_value"] == 1024.5
    assert final_setpoint_payload["units"] == "px"

    # The convergence Check (iter 2's last check) records the operator's
    # judgment + supporting evidence.
    convergence_check_payload = json.loads(step_rows[11]["payload"])
    assert convergence_check_payload["passed"] is True
    assert convergence_check_payload["source"] == "live_tomostream_centroid"
    assert convergence_check_payload["evidence"]["iteration"] == 2
    assert convergence_check_payload["evidence"]["offset_px"] == 0.5

    # ----- Drain the projection and assert the read-side record is operator-correct -----

    await _drain(db_pool)

    page = await bind_list(deps)(
        ListProcedures(kind="center_alignment"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    matching = [item for item in page.items if item.procedure_id == _PROCEDURE_ID]
    assert len(matching) == 1
    proc_summary = matching[0]
    assert proc_summary.name == "35-BM rotation-axis alignment (vessel-A bakeout pre-scan)"
    assert proc_summary.kind == "center_alignment"
    assert proc_summary.status == ProcedureStatus.COMPLETED.value
    assert proc_summary.steps_logbook_id == _STEPS_LOGBOOK_ID
    # All 4 target Assets surface in the read model for at-a-glance ops queries.
    assert set(proc_summary.target_asset_ids) == {
        _ASSET_AEROTECH_ABRS_ID,
        _ASSET_SAMPLE_TOP_X_ID,
        _ASSET_ORYX_5MP_ID,
        _ASSET_SCINTILLATOR_LUAG_ID,
    }
    assert proc_summary.parent_run_id is None  # standalone alignment, not Phase-of-Run
    assert proc_summary.last_status_changed_at == _NOW

    # ----- Reverse-direction filter: the target_asset_id GIN index works for
    #       "show me all procedures touching the Aerotech rotary stage" -----
    page_by_asset = await bind_list(deps)(
        ListProcedures(target_asset_id=_ASSET_AEROTECH_ABRS_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert any(item.procedure_id == _PROCEDURE_ID for item in page_by_asset.items)


# ---------------- Helpers ----------------


def _postgres_step_store(db_pool: asyncpg.Pool):
    """Build a PostgresStepStore for the BC-internal step writer.

    `wire_operation` constructs this normally from `deps.pool`; the
    scenario test exercises the slice handler directly via `bind_append`,
    so we construct the store here.
    """
    from cora.operation.aggregates.procedure import PostgresStepStore

    return PostgresStepStore(db_pool)


async def _read_steps(db_pool: asyncpg.Pool, procedure_id: UUID) -> list[asyncpg.Record]:
    async with db_pool.acquire() as conn:
        return await conn.fetch(
            """
            SELECT step_kind, payload, sampled_at
            FROM entries_operation_procedure_steps
            WHERE procedure_id = $1
            ORDER BY sampled_at
            """,
            procedure_id,
        )
