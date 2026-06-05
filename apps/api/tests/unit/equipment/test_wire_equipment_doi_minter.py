"""Unit tests for the Equipment BC's `DoiMinter` bootstrap wiring.

Per [[project-asset-persistent-id-write-design]] section 13.1 + Lock 10:
`wire_equipment` reads `Settings.datacite_repository_id` and wires the
inert `StubDoiMinter` when the field is None (the dev / test default).
The minter is attached BC-local at `deps.equipment.doi_minter` so the
`assign_asset_persistent_id` handler closure can read it, AND surfaced on the
returned `EquipmentHandlers.doi_minter` so the FastAPI lifespan stashes
it on `app.state.equipment.doi_minter` for test-override of the 502
mint-failure path. P1-7 covers the test-file naming convention.
"""

import pytest

from cora.equipment.adapters.stub_doi_minter import StubDoiMinter
from cora.equipment.wire import wire_equipment
from tests.unit._helpers import build_deps as _build_deps_shared

pytestmark = pytest.mark.timeout(60, method="thread")


@pytest.mark.unit
def test_wire_equipment_with_datacite_repository_id_none_wires_stub_doi_minter() -> None:
    deps = _build_deps_shared(ids=[])
    handlers = wire_equipment(deps)
    assert isinstance(handlers.doi_minter, StubDoiMinter)


@pytest.mark.unit
def test_wire_equipment_stores_doi_minter_on_app_state_equipment() -> None:
    deps = _build_deps_shared(ids=[])
    handlers = wire_equipment(deps)
    bc_local = getattr(deps, "equipment", None)
    assert bc_local is not None
    assert bc_local.doi_minter is handlers.doi_minter
    assert isinstance(bc_local.doi_minter, StubDoiMinter)


@pytest.mark.unit
@pytest.mark.skip(
    reason="DataCiteDoiMinter wiring lands in F.2 once production credentials gate is available"
)
def test_wire_equipment_with_datacite_repository_id_set_skips_stub() -> None:
    deps = _build_deps_shared(ids=[])
    deps.settings.datacite_repository_id = "test.repo"  # type: ignore[attr-defined]
    handlers = wire_equipment(deps)
    assert not isinstance(handlers.doi_minter, StubDoiMinter)
