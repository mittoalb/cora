"""Cross-BC unit tests for the defensive 409 exception handlers.

Each BC's `routes.py` registers a small family of FastAPI exception
handlers that translate domain / infra errors to HTTP responses.
Three of them are "essentially impossible in production with UUIDv7
ids" defensive 409 wrappers — the same 5-line `JSONResponse(...)`
shape repeated in three BCs:

  - access/routes.py:_handle_concurrency_conflict (lost optimistic-
    concurrency race)
  - data/routes.py:_handle_already_exists  (duplicate Dataset id)
  - decision/routes.py:_handle_already_exists (duplicate Decision id)

The underlying exception paths are exercised at decider level
(`tests/unit/<bc>/test_<verb>_decider.py`), but the wrapper itself
never fires through the integration / contract layers because the
real id generator is collision-free in practice. These direct
calls close that 6-line gap honestly: the handlers are real Python
code, so a real Python test asserting their output is the right
shape of coverage.

Importing private (`_handle_*`) symbols is intentional: the
handlers are module-private to the `routes.py` registration glue
but their *behaviour* is part of the public HTTP contract.
"""

# pyright: reportPrivateUsage=false

import json
from typing import Any
from uuid import uuid4

import pytest
from fastapi import status
from starlette.requests import Request

from cora.access.routes import _handle_concurrency_conflict
from cora.data.routes import _handle_already_exists as _data_handle_already_exists
from cora.decision.routes import _handle_already_exists as _decision_handle_already_exists


def _fake_request() -> Request:
    """Minimal Starlette Request with a valid ASGI scope. The handlers
    never read the request, so any well-formed scope works."""
    scope: dict[str, Any] = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "headers": [],
    }
    return Request(scope)


@pytest.mark.unit
async def test_access_concurrency_conflict_returns_409_with_detail() -> None:
    exc = RuntimeError(f"optimistic-concurrency lost on stream {uuid4()}")
    response = await _handle_concurrency_conflict(_fake_request(), exc)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert json.loads(bytes(response.body)) == {"detail": str(exc)}


@pytest.mark.unit
async def test_data_already_exists_returns_409_with_detail() -> None:
    exc = RuntimeError(f"Dataset {uuid4()} already exists")
    response = await _data_handle_already_exists(_fake_request(), exc)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert json.loads(bytes(response.body)) == {"detail": str(exc)}


@pytest.mark.unit
async def test_decision_already_exists_returns_409_with_detail() -> None:
    exc = RuntimeError(f"Decision {uuid4()} already exists")
    response = await _decision_handle_already_exists(_fake_request(), exc)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert json.loads(bytes(response.body)) == {"detail": str(exc)}
