"""End-to-end integration test: deprecate_capability against real Postgres.

Round-trip: define + version + deprecate + load_capability returns
the deprecated state with version preserved (the audit
signal of the last revision before deprecation).
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment.aggregates.capability import CapabilityStatus, load_capability
from cora.equipment.features import (
    define_capability,
    deprecate_capability,
    version_capability,
)
from cora.equipment.features.define_capability import DefineCapability
from cora.equipment.features.deprecate_capability import DeprecateCapability
from cora.equipment.features.version_capability import VersionCapability
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_deprecate_capability_persists_and_preserves_version_through_fold(
    db_pool: asyncpg.Pool,
) -> None:
    capability_id = UUID("01900000-0000-7000-8000-00000057fb01")
    defined_event_id = UUID("01900000-0000-7000-8000-00000057fb0e")
    versioned_event_id = UUID("01900000-0000-7000-8000-00000057fb0f")
    deprecated_event_id = UUID("01900000-0000-7000-8000-00000057fb10")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            capability_id,
            defined_event_id,
            versioned_event_id,
            deprecated_event_id,
        ],
    )

    await define_capability.bind(deps)(
        DefineCapability(name="X-ray Fluorescence Mapping"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await version_capability.bind(deps)(
        VersionCapability(capability_id=capability_id, version_tag="2026-Q2"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await deprecate_capability.bind(deps)(
        DeprecateCapability(capability_id=capability_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Capability", capability_id)
    assert version == 3
    assert [e.event_type for e in events] == [
        "CapabilityDefined",
        "CapabilityVersioned",
        "CapabilityDeprecated",
    ]
    deprecated = events[2]
    assert deprecated.event_id == deprecated_event_id

    state = await load_capability(deps.event_store, capability_id)
    assert state is not None
    assert state.status is CapabilityStatus.DEPRECATED
    # Audit signal: latest version_tag preserved through deprecation.
    assert state.version == "2026-Q2"
