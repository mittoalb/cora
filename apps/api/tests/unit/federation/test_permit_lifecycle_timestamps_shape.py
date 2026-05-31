"""Shape pin for `PermitLifecycleTimestamps`.

Frozen so callers cannot mutate it under cached references; field
shape pinned so future widening shows up as a deliberate change.
Mirrors the Path C precedent locked for Method / Capability /
Practice / Family / Calibration projection-sourced timestamps VOs.
"""

import dataclasses
from datetime import UTC, datetime

import pytest

from cora.federation.aggregates.permit import PermitLifecycleTimestamps

_NOW = datetime(2026, 5, 12, 14, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_permit_lifecycle_timestamps_is_immutable_dataclass() -> None:
    assert dataclasses.is_dataclass(PermitLifecycleTimestamps)
    field_names = {f.name for f in dataclasses.fields(PermitLifecycleTimestamps)}
    assert field_names == {
        "defined_at",
        "activated_at",
        "suspended_at",
        "resumed_at",
        "revoked_at",
    }

    instance = PermitLifecycleTimestamps(
        defined_at=_NOW,
        activated_at=None,
        suspended_at=None,
        resumed_at=None,
        revoked_at=None,
    )
    assert instance.defined_at == _NOW
    assert instance.activated_at is None
    assert instance.suspended_at is None
    assert instance.resumed_at is None
    assert instance.revoked_at is None

    with pytest.raises(dataclasses.FrozenInstanceError):
        instance.activated_at = _NOW  # type: ignore[misc]
