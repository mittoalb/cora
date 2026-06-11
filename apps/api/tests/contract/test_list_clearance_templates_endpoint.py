"""Contract tests for `GET /clearance-templates`.

Pins the wire shape: response envelope, query-param validation,
filter pass-through, and the authorize-port denial wiring. The
projection-fold + pagination behavior is exercised at the
integration tier in `tests/integration/test_list_clearance_templates_handler_postgres.py`;
this file only exercises the route surface (status codes,
schema, authz wiring).
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.safety.errors import UnauthorizedError
from cora.safety.features.list_clearance_templates.handler import (
    ClearanceTemplateListPage,
    ClearanceTemplateSummaryItem,
)
from cora.safety.features.list_clearance_templates.query import ListClearanceTemplates
from cora.safety.features.list_clearance_templates.route import (
    _get_handler as _get_list_clearance_templates_handler,  # pyright: ignore[reportPrivateUsage]
)


@pytest.mark.contract
def test_get_clearance_templates_returns_empty_page_when_projection_empty() -> None:
    """In-memory test deps have no Postgres pool; handler returns empty."""
    with TestClient(create_app()) as client:
        response = client.get("/clearance-templates")
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


@pytest.mark.contract
def test_get_clearance_templates_accepts_facility_code_filter() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/clearance-templates", params={"facility_code": "aps"})
    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.contract
@pytest.mark.parametrize("status_value", ["Draft", "Active", "Deprecated", "Withdrawn"])
def test_get_clearance_templates_accepts_each_status_filter(status_value: str) -> None:
    with TestClient(create_app()) as client:
        response = client.get("/clearance-templates", params={"status": status_value})
    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.contract
def test_get_clearance_templates_accepts_code_filter() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/clearance-templates", params={"code": "ESAF"})
    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.contract
def test_get_clearance_templates_accepts_full_filter_set() -> None:
    """All filters + cursor + limit at once should parse cleanly."""
    with TestClient(create_app()) as client:
        response = client.get(
            "/clearance-templates",
            params={
                "facility_code": "aps",
                "status": "Active",
                "code": "ESAF",
                "limit": "25",
            },
        )
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


@pytest.mark.contract
def test_get_clearance_templates_accepts_limit_within_range() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/clearance-templates", params={"limit": "10"})
    assert response.status_code == 200


@pytest.mark.contract
def test_get_clearance_templates_rejects_limit_above_cap_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/clearance-templates", params={"limit": "101"})
    assert response.status_code == 422


@pytest.mark.contract
def test_get_clearance_templates_rejects_limit_below_one_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/clearance-templates", params={"limit": "0"})
    assert response.status_code == 422


@pytest.mark.contract
def test_get_clearance_templates_rejects_invalid_status_with_422() -> None:
    """'Inactive' is NOT in the Literal (Draft / Active / Deprecated / Withdrawn only)."""
    with TestClient(create_app()) as client:
        response = client.get("/clearance-templates", params={"status": "Inactive"})
    assert response.status_code == 422


@pytest.mark.contract
def test_get_clearance_templates_rejects_invalid_cursor_with_422() -> None:
    """Malformed cursor (corrupt base64 / missing separator / etc.) surfaces
    as `InvalidCursorError` at the handler and 422 via the exception handler."""
    with TestClient(create_app()) as client:
        response = client.get(
            "/clearance-templates",
            params={"cursor": "this-is-not-a-valid-cursor"},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_get_clearance_templates_returns_populated_page_from_handler() -> None:
    """Stubbed handler returns one row; route serializes through
    `ClearanceTemplateSummaryDTO` with `next_cursor` round-tripped."""
    app = create_app()
    template_id = uuid4()
    defined_at = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
    page = ClearanceTemplateListPage(
        items=[
            ClearanceTemplateSummaryItem(
                template_id=template_id,
                code="ESAF",
                title="Experimental Safety Assessment Form",
                facility_code="aps",
                version=1,
                status="Active",
                defined_at=defined_at,
            ),
        ],
        next_cursor="opaque-next-cursor-token",
    )

    async def fake_handler(*args: object, **kwargs: object) -> ClearanceTemplateListPage:
        _ = (args, kwargs)
        return page

    app.dependency_overrides[_get_list_clearance_templates_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.get("/clearance-templates")

    assert response.status_code == 200
    body = response.json()
    assert body["next_cursor"] == "opaque-next-cursor-token"
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["template_id"] == str(template_id)
    assert item["code"] == "ESAF"
    assert item["title"] == "Experimental Safety Assessment Form"
    assert item["facility_code"] == "aps"
    assert item["version"] == 1
    assert item["status"] == "Active"
    assert item["defined_at"].startswith("2026-06-10T12:00:00")


@pytest.mark.contract
def test_get_clearance_templates_forwards_cursor_and_filters_to_handler() -> None:
    """Pin the wiring: route should build a `ListClearanceTemplates` query
    carrying cursor + limit + facility_code + status + code from the URL."""
    app = create_app()
    captured: dict[str, Any] = {}

    async def fake_handler(
        query: ListClearanceTemplates, **kwargs: object
    ) -> ClearanceTemplateListPage:
        _ = kwargs
        captured["query"] = query
        return ClearanceTemplateListPage(items=[], next_cursor=None)

    app.dependency_overrides[_get_list_clearance_templates_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.get(
            "/clearance-templates",
            params={
                "cursor": "opaque-cursor-token",
                "limit": "25",
                "facility_code": "aps",
                "status": "Active",
                "code": "ESAF",
            },
        )

    assert response.status_code == 200
    query = captured["query"]
    assert isinstance(query, ListClearanceTemplates)
    assert query.cursor == "opaque-cursor-token"
    assert query.limit == 25
    assert query.facility_code == "aps"
    assert query.status == "Active"
    assert query.code == "ESAF"


@pytest.mark.contract
def test_get_clearance_templates_defaults_limit_to_fifty_when_omitted() -> None:
    """Omitting `limit` should yield the documented default (50)."""
    app = create_app()
    captured: dict[str, Any] = {}

    async def fake_handler(
        query: ListClearanceTemplates, **kwargs: object
    ) -> ClearanceTemplateListPage:
        _ = kwargs
        captured["query"] = query
        return ClearanceTemplateListPage(items=[], next_cursor=None)

    app.dependency_overrides[_get_list_clearance_templates_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.get("/clearance-templates")

    assert response.status_code == 200
    assert captured["query"].limit == 50
    assert captured["query"].cursor is None
    assert captured["query"].facility_code is None
    assert captured["query"].status is None
    assert captured["query"].code is None


@pytest.mark.contract
def test_get_clearance_templates_returns_403_when_authorize_denies() -> None:
    """Route documents 403 in `responses=`; this pins the wire-level path."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> Any:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_list_clearance_templates_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.get("/clearance-templates")
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"
