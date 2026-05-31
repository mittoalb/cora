"""Shape pin for `CredentialLifecycleTimestamps`.

Frozen so callers cannot mutate it under cached references; field
shape pinned so future widening (e.g., adding `revoked_at` when the
revocation projection column lands) shows up as a deliberate change.
Mirrors the Path C precedent locked for Method / Capability /
Practice / Family / Calibration projection-sourced timestamps VOs.
"""

import dataclasses
from datetime import UTC, datetime

import pytest

from cora.federation.aggregates.credential import CredentialLifecycleTimestamps

_NOW = datetime(2026, 5, 12, 14, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_credential_lifecycle_timestamps_is_immutable_dataclass() -> None:
    assert dataclasses.is_dataclass(CredentialLifecycleTimestamps)
    field_names = {f.name for f in dataclasses.fields(CredentialLifecycleTimestamps)}
    assert field_names == {"registered_at", "rotation_started_at"}

    instance = CredentialLifecycleTimestamps(
        registered_at=_NOW,
        rotation_started_at=None,
    )
    assert instance.registered_at == _NOW
    assert instance.rotation_started_at is None

    with pytest.raises(dataclasses.FrozenInstanceError):
        instance.rotation_started_at = _NOW  # type: ignore[misc]
