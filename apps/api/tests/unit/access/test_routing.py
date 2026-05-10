"""Unit tests for `cora.access._routing.get_principal_id`.

Direct invocation of the FastAPI dependency function; the
`x_principal_id` parameter is what FastAPI's `Header(...)` machinery
passes at request time. We test that:
  - Header value (UUID) is returned as-is.
  - Header absent (None) falls back to SYSTEM_PRINCIPAL_ID.

Pydantic UUID-format validation happens BEFORE this function runs
(FastAPI's request layer); contract tests cover the malformed-header
422 path end-to-end.
"""

from uuid import UUID, uuid4

import pytest

from cora.access._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.access._routing import get_principal_id


@pytest.mark.unit
def test_get_principal_id_returns_header_uuid_when_present() -> None:
    pid = uuid4()
    assert get_principal_id(x_principal_id=pid) == pid


@pytest.mark.unit
def test_get_principal_id_falls_back_to_system_when_header_absent() -> None:
    """Phase 1 fallback semantics preserved: existing tests + dev calls
    that don't set the header continue to use SYSTEM_PRINCIPAL_ID."""
    assert get_principal_id(x_principal_id=None) == SYSTEM_PRINCIPAL_ID


@pytest.mark.unit
def test_get_principal_id_does_not_validate_actor_existence() -> None:
    """The function trusts the header value as-is (trust-the-proxy
    pattern). It does NOT verify that the UUID corresponds to a
    registered Actor — that's a Trust-BC concern at the Authorize
    gate. Pinned so a future "validate principal exists" check has
    to do so deliberately at the right layer."""
    arbitrary = UUID("01900000-0000-7000-8000-000000007777")
    assert get_principal_id(x_principal_id=arbitrary) == arbitrary
