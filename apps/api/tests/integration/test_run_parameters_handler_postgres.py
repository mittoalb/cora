"""End-to-end integration test: 6g-c parameter flow against real Postgres.

Exercises the cross-aggregate parameter resolution at start_run:
  - Plan.default_parameters (set via 6g-b update_plan_default_parameters)
  - merged with command.override_parameters (RFC 7396 via merge_patch)
  - validated against Method.parameters_schema (set via 6g-a)
  - persisted in RunStarted payload (override_parameters + effective_parameters + triggered_by)
  - folded into Run state on load
  - projection's `override_parameters_present` column flips TRUE
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment.aggregates.asset import AssetLevel
from cora.equipment.features import (
    add_asset_capability,
    define_capability,
    register_asset,
)
from cora.equipment.features.add_asset_capability import AddAssetCapability
from cora.equipment.features.define_capability import DefineCapability
from cora.equipment.features.register_asset import RegisterAsset
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.recipe.features import (
    define_method,
    define_plan,
    define_practice,
    update_method_parameters_schema,
    update_plan_default_parameters,
)
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_plan import DefinePlan
from cora.recipe.features.define_practice import DefinePractice
from cora.recipe.features.update_method_parameters_schema import (
    UpdateMethodParametersSchema,
)
from cora.recipe.features.update_plan_default_parameters import (
    UpdatePlanDefaultParameters,
)
from cora.run._projections import register_run_projections
from cora.run.aggregates.run import InvalidRunParametersError, load_run
from cora.run.features import start_run
from cora.run.features.start_run import StartRun
from cora.subject.features import mount_subject, register_subject
from cora.subject.features.mount_subject import MountSubject
from cora.subject.features.register_subject import RegisterSubject
from tests.integration._helpers import build_postgres_deps
from tests.unit.subject._asset_helper import seed_active_asset

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _build_deps(db_pool: asyncpg.Pool, ids: list[UUID]) -> Kernel:
    return build_postgres_deps(db_pool, now=_NOW, ids=ids)


async def _drain_run_projections(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_run_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


def _energy_schema() -> dict[str, Any]:
    return {
        "$schema": _DRAFT,
        "type": "object",
        "properties": {
            "energy_kev": {"type": "number", "minimum": 5, "maximum": 50},
            "exposure_ms": {"type": "integer", "minimum": 1},
        },
    }


async def _seed_full_chain(
    db_pool: asyncpg.Pool,
    *,
    method_schema: dict[str, Any] | None,
    plan_defaults: dict[str, Any] | None,
) -> tuple[UUID, UUID]:
    """Seed Capability + Method (with optional schema) + Practice +
    Asset + Plan (with optional defaults) + Subject (Mounted) into PG.
    Returns (plan_id, subject_id). Each call uses fresh UUIDs (uuid4)
    so multiple test fns don't collide on the same streams."""
    # Generate enough event ids for every step.
    ids = [uuid4() for _ in range(40)]
    deps = _build_deps(db_pool, ids)

    cap_id = await define_capability.bind(deps)(
        DefineCapability(name="FlyMotion"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    method_id = await define_method.bind(deps)(
        DefineMethod(name="Test Method", needs_capabilities=frozenset({cap_id})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    if method_schema is not None:
        await update_method_parameters_schema.bind(deps)(
            UpdateMethodParametersSchema(method_id=method_id, parameters_schema=method_schema),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    site_id = uuid4()
    practice_id = await define_practice.bind(deps)(
        DefinePractice(name="Test Practice", method_id=method_id, site_id=site_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    asset_id = await register_asset.bind(deps)(
        RegisterAsset(name="TestAsset", level=AssetLevel.ENTERPRISE, parent_id=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_capability.bind(deps)(
        AddAssetCapability(asset_id=asset_id, capability_id=cap_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    plan_id = await define_plan.bind(deps)(
        DefinePlan(
            name="32-ID FlyScan",
            practice_id=practice_id,
            asset_ids=frozenset({asset_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    if plan_defaults:
        await update_plan_default_parameters.bind(deps)(
            UpdatePlanDefaultParameters(plan_id=plan_id, default_parameters_patch=plan_defaults),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    subject_id = await register_subject.bind(deps)(
        RegisterSubject(name="PorousCeramicSample-A"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    mount_asset_id = await seed_active_asset(
        deps.event_store, now=_NOW, correlation_id=_CORRELATION_ID
    )
    await mount_subject.bind(deps)(
        MountSubject(subject_id=subject_id, asset_id=mount_asset_id, reason="test"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    return plan_id, subject_id


@pytest.mark.integration
async def test_start_run_merges_defaults_and_overrides_into_effective_parameters(
    db_pool: asyncpg.Pool,
) -> None:
    """Plan defaults + Run overrides merge per RFC 7396; resolved set
    persists in RunStarted and folds onto Run state."""
    plan_id, subject_id = await _seed_full_chain(
        db_pool,
        method_schema=_energy_schema(),
        plan_defaults={"energy_kev": 12.0, "exposure_ms": 100},
    )
    deps = _build_deps(db_pool, [uuid4(), uuid4()])  # run id + RunStarted event id

    run_id = await start_run.bind(deps)(
        StartRun(
            name="Run-with-overrides",
            plan_id=plan_id,
            subject_id=subject_id,
            override_parameters={"exposure_ms": 250},
            triggered_by="operator:opid:5",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    loaded = await load_run(deps.event_store, run_id)
    assert loaded is not None
    assert loaded.override_parameters == {"exposure_ms": 250}
    # Defaults' energy_kev preserved; override's exposure_ms wins.
    assert loaded.effective_parameters == {"energy_kev": 12.0, "exposure_ms": 250}
    assert loaded.triggered_by == "operator:opid:5"

    await _drain_run_projections(db_pool)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT override_parameters_present FROM proj_run_summary WHERE run_id = $1",
            run_id,
        )
    assert row is not None
    assert row["override_parameters_present"] is True


@pytest.mark.integration
async def test_start_run_with_no_overrides_uses_plan_defaults(
    db_pool: asyncpg.Pool,
) -> None:
    """Operator omits overrides -> effective_parameters == Plan defaults."""
    plan_id, subject_id = await _seed_full_chain(
        db_pool,
        method_schema=_energy_schema(),
        plan_defaults={"energy_kev": 12.0, "exposure_ms": 100},
    )
    deps = _build_deps(db_pool, [uuid4(), uuid4()])

    run_id = await start_run.bind(deps)(
        StartRun(name="Run-defaults-only", plan_id=plan_id, subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    loaded = await load_run(deps.event_store, run_id)
    assert loaded is not None
    assert loaded.override_parameters == {}
    assert loaded.effective_parameters == {"energy_kev": 12.0, "exposure_ms": 100}

    await _drain_run_projections(db_pool)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT override_parameters_present FROM proj_run_summary WHERE run_id = $1",
            run_id,
        )
    assert row is not None
    # Defaults straight, no overrides supplied -> projection FALSE.
    assert row["override_parameters_present"] is False


@pytest.mark.integration
async def test_start_run_rejects_overrides_violating_method_schema(
    db_pool: asyncpg.Pool,
) -> None:
    """Override pushes effective_parameters out of schema bounds ->
    InvalidRunParametersError; no event appended."""
    plan_id, subject_id = await _seed_full_chain(
        db_pool,
        method_schema=_energy_schema(),
        plan_defaults={"energy_kev": 12.0},
    )
    deps = _build_deps(db_pool, [uuid4(), uuid4()])

    with pytest.raises(InvalidRunParametersError):
        await start_run.bind(deps)(
            StartRun(
                name="Run-bad",
                plan_id=plan_id,
                subject_id=subject_id,
                override_parameters={"energy_kev": 1.0},
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


# NOTE: an old `test_start_run_permissive_when_method_has_no_schema` test
# lived here pre-audit. It was replaced by the strict-mode pair
# (test_start_run_strict_when_method_has_no_schema +
# test_start_run_accepts_no_schema_when_no_overrides_and_no_defaults)
# in the post-6g audit reversal commit. See [[project_run_parameters_design]]
# §audit-correction.
