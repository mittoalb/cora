"""Contract tests for `POST /clearance-templates` (define_clearance_template).

Covers create-style basics (request schema, response shape, status codes),
the Pydantic min/max length + regex on `code` / `title` / `facility_code`
(-> 422), the cross-BC ClearanceTemplateFacilityNotFound mapping when
the slug does not resolve (-> 404), the domain-VO validation when
whitespace-only slips past Pydantic (-> 400), the AlreadyExists defensive
guard (-> 409 via dependency_overrides), the Authorize-port denial
mapping (-> 403), and the Idempotency-Key header round-trip semantics
(replay returns the cached body; different body with same key -> 422).

The TestClient app bootstraps with `SELF_FACILITY_CODE` defaulting to
`"cora"`, so happy-path requests bind to the self-Facility row seeded
at lifespan. The not-found contract uses an unseeded slug.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.safety.aggregates.clearance_template import (
    CLEARANCE_TEMPLATE_CODE_MAX_LENGTH,
    CLEARANCE_TEMPLATE_TITLE_MAX_LENGTH,
    ClearanceTemplateAlreadyExistsError,
)
from cora.safety.errors import UnauthorizedError
from cora.safety.features.define_clearance_template.route import (
    _get_handler as _get_define_clearance_template_handler,  # pyright: ignore[reportPrivateUsage]
)

_FACILITY_CODE = "cora"


def _body(
    *,
    code: str = "radiation-safety-form",
    title: str = "Radiation Safety Form",
    facility_code: str = _FACILITY_CODE,
    external_ref: str | None = None,
) -> dict[str, object]:
    body: dict[str, object] = {
        "code": code,
        "title": title,
        "facility_code": facility_code,
    }
    if external_ref is not None:
        body["external_ref"] = external_ref
    return body


@pytest.mark.contract
def test_post_clearance_templates_returns_201_with_template_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/clearance-templates", json=_body())
    assert response.status_code == 201, response.text
    body = response.json()
    assert "template_id" in body
    UUID(body["template_id"])


@pytest.mark.contract
def test_post_clearance_templates_rejects_missing_required_fields_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/clearance-templates", json={})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_clearance_templates_rejects_missing_code_with_422() -> None:
    body = _body()
    del body["code"]
    with TestClient(create_app()) as client:
        response = client.post("/clearance-templates", json=body)
    assert response.status_code == 422


@pytest.mark.contract
def test_post_clearance_templates_rejects_missing_title_with_422() -> None:
    body = _body()
    del body["title"]
    with TestClient(create_app()) as client:
        response = client.post("/clearance-templates", json=body)
    assert response.status_code == 422


@pytest.mark.contract
def test_post_clearance_templates_rejects_missing_facility_code_with_422() -> None:
    body = _body()
    del body["facility_code"]
    with TestClient(create_app()) as client:
        response = client.post("/clearance-templates", json=body)
    assert response.status_code == 422


@pytest.mark.contract
def test_post_clearance_templates_rejects_empty_code_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/clearance-templates", json=_body(code=""))
    assert response.status_code == 422


@pytest.mark.contract
def test_post_clearance_templates_rejects_too_long_code_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/clearance-templates",
            json=_body(code="a" * (CLEARANCE_TEMPLATE_CODE_MAX_LENGTH + 1)),
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_clearance_templates_rejects_too_long_title_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/clearance-templates",
            json=_body(title="x" * (CLEARANCE_TEMPLATE_TITLE_MAX_LENGTH + 1)),
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_clearance_templates_rejects_overlong_code_with_422() -> None:
    """Pydantic length cap rejects codes over CLEARANCE_TEMPLATE_CODE_MAX_LENGTH (50)
    at the API boundary, before the bounded_name VO runs."""
    with TestClient(create_app()) as client:
        response = client.post("/clearance-templates", json=_body(code="a" * 51))
    assert response.status_code == 422


@pytest.mark.contract
@pytest.mark.parametrize(
    "bad_facility_code",
    ["APS", "_underscore", "with space", "a" * 33, ""],
)
def test_post_clearance_templates_rejects_malformed_facility_code_with_422(
    bad_facility_code: str,
) -> None:
    """FacilityCode regex (lowercase ASCII alphanumeric + dash, 1-32 chars)
    enforced at the Pydantic boundary."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/clearance-templates",
            json=_body(facility_code=bad_facility_code),
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_clearance_templates_returns_404_when_facility_code_unseeded() -> None:
    """Cross-BC binding: an unknown but well-formed slug surfaces as
    ClearanceTemplateFacilityNotFoundError -> 404."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/clearance-templates",
            json=_body(facility_code="unseeded"),
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_clearance_templates_returns_409_on_already_exists() -> None:
    """Defensive guard: a ClearanceTemplateAlreadyExistsError bubbles as 409 conflict."""
    app = create_app()
    existing_id = uuid4()

    async def fake_handler(*args: object, **kwargs: object) -> UUID:
        _ = (args, kwargs)
        raise ClearanceTemplateAlreadyExistsError(existing_id)

    app.dependency_overrides[_get_define_clearance_template_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post("/clearance-templates", json=_body())
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_clearance_templates_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> UUID:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_define_clearance_template_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post("/clearance-templates", json=_body())
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"


@pytest.mark.contract
def test_post_clearance_templates_without_key_creates_distinct_each_call() -> None:
    """Without an Idempotency-Key, distinct stream identities require
    distinct (facility_code, code) tuples; same body posted twice
    surfaces the AlreadyExists 409 path covered above."""
    with TestClient(create_app()) as client:
        r1 = client.post("/clearance-templates", json=_body(code="form-a"))
        r2 = client.post("/clearance-templates", json=_body(code="form-b"))
    assert r1.status_code == 201, r1.text
    assert r2.status_code == 201, r2.text
    assert r1.json()["template_id"] != r2.json()["template_id"]


@pytest.mark.contract
def test_post_clearance_templates_same_key_and_body_returns_same_template_id() -> None:
    """Idempotency-Key replay: same key + same body returns the cached
    response body verbatim instead of re-creating the template."""
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "ct-1"}
        r1 = client.post("/clearance-templates", json=_body(), headers=headers)
        r2 = client.post("/clearance-templates", json=_body(), headers=headers)
    assert r1.status_code == 201, r1.text
    assert r2.status_code == 201, r2.text
    assert r1.json()["template_id"] == r2.json()["template_id"]


@pytest.mark.contract
def test_post_clearance_templates_same_key_different_body_returns_422() -> None:
    """Idempotency-Key reuse with a different body trips the
    `with_idempotency` hash check and returns 422."""
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "ct-2"}
        r1 = client.post(
            "/clearance-templates",
            json=_body(code="form-x", title="Form X"),
            headers=headers,
        )
        r2 = client.post(
            "/clearance-templates",
            json=_body(code="form-y", title="Form Y"),
            headers=headers,
        )
    assert r1.status_code == 201, r1.text
    assert r2.status_code == 422
    body = r2.json()
    assert "detail" in body
    assert "idempotency-key" in body["detail"].lower()


@pytest.mark.contract
def test_post_clearance_templates_different_keys_create_distinct_templates() -> None:
    with TestClient(create_app()) as client:
        r1 = client.post(
            "/clearance-templates",
            json=_body(code="form-alpha"),
            headers={"Idempotency-Key": "ct-A"},
        )
        r2 = client.post(
            "/clearance-templates",
            json=_body(code="form-beta"),
            headers={"Idempotency-Key": "ct-B"},
        )
    assert r1.status_code == 201, r1.text
    assert r2.status_code == 201, r2.text
    assert r1.json()["template_id"] != r2.json()["template_id"]
