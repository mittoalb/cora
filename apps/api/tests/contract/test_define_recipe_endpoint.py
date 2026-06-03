"""Contract tests for `POST /recipes`.

Recipe is a deployment-bound executable step sequence anchored on a
Capability. The endpoint loads the referenced Capability + validates
BindingRef integrity against its parameters_schema before persisting.
"""

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app

_DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
_DEFAULT_STEPS: list[dict[str, object]] = [
    {"kind": "setpoint", "address": "dev:rot:val", "value": 1.0, "verify": False},
]


def _capability_body(
    code: str = "cora.capability.tomo",
    name: str = "Tomo",
    parameters_schema: dict[str, object] | None = None,
) -> dict[str, object]:
    body: dict[str, object] = {
        "code": code,
        "name": name,
        "required_affordances": [],
        "executor_shapes": ["Method", "Procedure"],
    }
    if parameters_schema is not None:
        body["parameters_schema"] = parameters_schema
    return body


def _schema_with_angle() -> dict[str, object]:
    return {
        "$schema": _DRAFT_2020_12,
        "type": "object",
        "properties": {"angle": {"type": "number"}},
        "required": ["angle"],
    }


def _recipe_body(
    *,
    capability_id: str,
    name: str = "TomoRecipe",
    steps: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "name": name,
        "capability_id": capability_id,
        "steps": {"steps": steps if steps is not None else _DEFAULT_STEPS},
    }


@pytest.mark.contract
def test_post_recipes_201_creates_recipe_against_existing_capability() -> None:
    with TestClient(create_app()) as client:
        cap = client.post("/capabilities", json=_capability_body()).json()
        response = client.post("/recipes", json=_recipe_body(capability_id=cap["capability_id"]))
    assert response.status_code == 201
    assert "recipe_id" in response.json()


@pytest.mark.contract
def test_post_recipes_404_when_capability_missing() -> None:
    with TestClient(create_app()) as client:
        bogus = "01900000-0000-7000-8000-deadbeefcafe"
        response = client.post("/recipes", json=_recipe_body(capability_id=bogus))
    assert response.status_code == 404


@pytest.mark.contract
def test_post_recipes_422_when_binding_ref_unknown() -> None:
    with TestClient(create_app()) as client:
        cap = client.post(
            "/capabilities", json=_capability_body(parameters_schema=_schema_with_angle())
        ).json()
        response = client.post(
            "/recipes",
            json=_recipe_body(
                capability_id=cap["capability_id"],
                steps=[
                    {
                        "kind": "setpoint",
                        "address": "dev:rot:val",
                        "value": {"__binding__": "enrgy"},
                        "verify": False,
                    }
                ],
            ),
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_recipes_422_when_request_body_missing_steps() -> None:
    with TestClient(create_app()) as client:
        cap = client.post("/capabilities", json=_capability_body()).json()
        response = client.post(
            "/recipes",
            json={"name": "X", "capability_id": cap["capability_id"]},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_recipes_400_when_steps_empty() -> None:
    with TestClient(create_app()) as client:
        cap = client.post("/capabilities", json=_capability_body()).json()
        response = client.post(
            "/recipes",
            json=_recipe_body(capability_id=cap["capability_id"], steps=[]),
        )
    assert response.status_code == 400


@pytest.mark.contract
def test_post_recipes_same_idempotency_key_returns_same_recipe_id() -> None:
    with TestClient(create_app()) as client:
        cap = client.post("/capabilities", json=_capability_body()).json()
        headers = {"Idempotency-Key": "rk-1"}
        r1 = client.post(
            "/recipes",
            json=_recipe_body(capability_id=cap["capability_id"]),
            headers=headers,
        )
        r2 = client.post(
            "/recipes",
            json=_recipe_body(capability_id=cap["capability_id"]),
            headers=headers,
        )
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["recipe_id"] == r2.json()["recipe_id"]
