"""Contract tests for `POST /procedures/from-recipe`.

End-to-end through TestClient: register a Capability, register a
Recipe against that Capability, then exercise the Operation BC
register_procedure_from_recipe path covering 201 happy / 404 missing
Recipe / 409 executor-mismatch / 422 stale Capability schema.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app

_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _capability_body(
    code: str = "cora.capability.rec_proc",
    parameters_schema: dict[str, Any] | None = None,
    executor_shapes: list[str] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "code": code,
        "name": "TestCap",
        "required_affordances": [],
        "executor_shapes": executor_shapes or ["Method", "Procedure"],
    }
    if parameters_schema is not None:
        body["parameters_schema"] = parameters_schema
    return body


def _recipe_body(capability_id: str, with_binding: bool = False) -> dict[str, Any]:
    value: Any = {"__binding__": "angle"} if with_binding else 1.0
    return {
        "name": "R",
        "capability_id": capability_id,
        "steps": {
            "steps": [{"kind": "setpoint", "address": "dev:x", "value": value, "verify": False}],
        },
    }


def _register_body(recipe_id: str, bindings: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "name": "P",
        "kind": "bakeout",
        "target_asset_ids": [],
        "parent_run_id": None,
        "recipe_id": recipe_id,
        "bindings": bindings or {},
    }


@pytest.mark.contract
def test_post_procedures_from_recipe_201_creates_procedure() -> None:
    with TestClient(create_app()) as client:
        cap = client.post("/capabilities", json=_capability_body()).json()
        recipe = client.post("/recipes", json=_recipe_body(cap["capability_id"])).json()
        response = client.post("/procedures/from-recipe", json=_register_body(recipe["recipe_id"]))
    assert response.status_code == 201
    assert "procedure_id" in response.json()


@pytest.mark.contract
def test_post_procedures_from_recipe_404_when_recipe_missing() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/procedures/from-recipe",
            json=_register_body("01900000-0000-7000-8000-deadbeefcafe"),
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_procedures_from_recipe_409_when_capability_excludes_procedure() -> None:
    with TestClient(create_app()) as client:
        cap = client.post(
            "/capabilities",
            json=_capability_body(code="cora.capability.method_only", executor_shapes=["Method"]),
        ).json()
        recipe = client.post("/recipes", json=_recipe_body(cap["capability_id"])).json()
        response = client.post("/procedures/from-recipe", json=_register_body(recipe["recipe_id"]))
    assert response.status_code == 409


@pytest.mark.contract
def test_post_procedures_from_recipe_422_when_capability_schema_drifted() -> None:
    """Anti-hook 5 expansion-time half via REST: 422 + the stale-Capability error.

    The handler raises RecipeBindingsStaleAgainstCurrentCapabilityError
    when the Capability has been re-versioned since the Recipe was
    written and a binding name dropped from parameters_schema.
    """
    with TestClient(create_app()) as client:
        # Capability with `angle` schema; Recipe binds it.
        cap_v1 = client.post(
            "/capabilities",
            json=_capability_body(
                parameters_schema={
                    "$schema": _DRAFT,
                    "type": "object",
                    "properties": {"angle": {"type": "number"}},
                },
            ),
        ).json()
        recipe = client.post(
            "/recipes",
            json=_recipe_body(cap_v1["capability_id"], with_binding=True),
        ).json()
        # Version the Capability to DROP `angle` (now only `energy`).
        client.post(
            f"/capabilities/{cap_v1['capability_id']}/version",
            json={
                "version_tag": "v2",
                "required_affordances": [],
                "executor_shapes": ["Method", "Procedure"],
                "parameters_schema": {
                    "$schema": _DRAFT,
                    "type": "object",
                    "properties": {"energy": {"type": "number"}},
                },
            },
        )
        response = client.post(
            "/procedures/from-recipe",
            json=_register_body(recipe["recipe_id"], bindings={"angle": 30.0}),
        )
    assert response.status_code == 422
    assert "stale" in response.json()["detail"].lower()
