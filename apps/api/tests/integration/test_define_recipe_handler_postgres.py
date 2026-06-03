"""End-to-end integration test: define_recipe handler against real Postgres.

Pinned: Recipe step sequence round-trips through jsonb via the wire
format (`{steps: [{kind: setpoint|action|check, ...}]}`). The Recipe
stream is keyed by `recipe_id`; the referenced Capability stream
must exist (seeded via `seed_capability_postgres`) for the handler's
cross-aggregate fan-out to resolve. BindingRef-sentinel wire round-trip
(`{__binding__: name}`) is exercised at the unit tier in
`test_recipe_body.py` and `test_recipe_body_roundtrip_properties.py`;
this integration test stays on literal values so the seeded Capability
need not declare a parameters_schema.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.recipe.aggregates.recipe import RecipeSetpointStep
from cora.recipe.features import define_recipe
from cora.recipe.features.define_recipe import DefineRecipe
from tests.integration._helpers import build_postgres_deps, seed_capability_postgres

_NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_define_recipe_persists_recipe_defined_event(db_pool: asyncpg.Pool) -> None:
    recipe_id = UUID("01900000-0000-7000-8000-00000056fa01")
    event_id = UUID("01900000-0000-7000-8000-00000056fa0e")
    capability_id = UUID("01900000-0000-7000-8000-00000056fa0c")

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[recipe_id, event_id])
    await seed_capability_postgres(deps.event_store, capability_id)

    returned_id = await define_recipe.bind(deps)(
        DefineRecipe(
            name="TomoRecipe",
            capability_id=capability_id,
            steps=(
                RecipeSetpointStep(address="dev:rot:val", value=1.0),
                RecipeSetpointStep(address="dev:z", value=2.5, verify=True),
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned_id == recipe_id

    events, version = await deps.event_store.load("Recipe", recipe_id)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "RecipeDefined"
    assert stored.payload["recipe_id"] == str(recipe_id)
    assert stored.payload["capability_id"] == str(capability_id)
    assert stored.payload["name"] == "TomoRecipe"
    # Wire-format step sequence survives jsonb round-trip.
    assert stored.payload["steps"]["steps"][0]["address"] == "dev:rot:val"
    assert stored.payload["steps"]["steps"][1]["value"] == 2.5
    assert stored.payload["steps"]["steps"][1]["verify"] is True
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.event_id == event_id
    assert stored.metadata == {"command": "DefineRecipe"}
    assert stored.occurred_at == _NOW
