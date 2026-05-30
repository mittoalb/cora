"""Application-handler tests for the `get_permit` query slice.

Covers the two paths reachable without a Postgres pool:

  - Authz Deny -> `UnauthorizedError` (stream untouched).
  - No pool wired (in-memory test env) -> `PermitNotFoundError`.

The 200 happy path requires the `proj_federation_permit_summary`
projection and is covered end-to-end via the contract test against
`TestClient(create_app())` plus an `app.dependency_overrides` injected
fake handler returning a synthesized `PermitView`.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.federation.aggregates.permit import PermitNotFoundError
from cora.federation.errors import UnauthorizedError
from cora.federation.features import get_permit
from cora.federation.features.get_permit import GetPermit
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_PERMIT_ID = UUID("01900000-0000-7000-8000-000000fed901")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.unit
async def test_get_permit_handler_raises_unauthorized_on_deny() -> None:
    deps = _build_deps_shared(ids=[], now=_NOW, deny=True)
    handler = get_permit.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            GetPermit(permit_id=_PERMIT_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_get_permit_handler_raises_not_found_when_no_pool() -> None:
    """In-memory test deps have pool=None; handler short-circuits to PermitNotFoundError."""
    deps = _build_deps_shared(ids=[], now=_NOW)
    handler = get_permit.bind(deps)
    with pytest.raises(PermitNotFoundError):
        await handler(
            GetPermit(permit_id=_PERMIT_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
