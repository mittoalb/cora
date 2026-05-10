"""Unit tests for `cora.trust._routing.get_principal_id`.

Mirror of the Access BC's test_routing — same trust-the-proxy
extraction semantics. Both BCs share the helper shape today;
extraction to `cora/infrastructure/_routing.py` lands when a third
BC needs it (Rule of Three).
"""

from uuid import UUID, uuid4

import pytest

from cora.trust._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.trust._routing import get_principal_id


@pytest.mark.unit
def test_get_principal_id_returns_header_uuid_when_present() -> None:
    pid = uuid4()
    assert get_principal_id(x_principal_id=pid) == pid


@pytest.mark.unit
def test_get_principal_id_falls_back_to_system_when_header_absent() -> None:
    assert get_principal_id(x_principal_id=None) == SYSTEM_PRINCIPAL_ID


@pytest.mark.unit
def test_get_principal_id_does_not_validate_actor_existence() -> None:
    """Trust-the-proxy: the function returns the header value as-is.
    Pinned so a future validity check has to be deliberate."""
    arbitrary = UUID("01900000-0000-7000-8000-000000008888")
    assert get_principal_id(x_principal_id=arbitrary) == arbitrary
