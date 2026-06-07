"""Shape pin for `SealLifecycleTimestamps`.

Frozen so callers cannot mutate it under cached references; field
shape pinned so future widening shows up as a deliberate change.
Seal is the per-facility singleton without revocation, so the VO
carries `initialized_at`, `last_signed_at`, and the most-recent
signer actor id (the latter two are None until the first
`SealPointerSigned`).
"""

import dataclasses
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.federation.aggregates.seal import SealLifecycleTimestamps

_NOW = datetime(2026, 5, 12, 14, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_seal_lifecycle_timestamps_is_immutable_dataclass() -> None:
    assert dataclasses.is_dataclass(SealLifecycleTimestamps)
    field_names = {f.name for f in dataclasses.fields(SealLifecycleTimestamps)}
    assert field_names == {
        "last_signed_at",
        "last_signed_by",
    }

    instance = SealLifecycleTimestamps(
        last_signed_at=None,
        last_signed_by=None,
    )
    assert instance.last_signed_at is None
    assert instance.last_signed_by is None

    populated = SealLifecycleTimestamps(
        last_signed_at=_NOW,
        last_signed_by=uuid4(),
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        populated.last_signed_at = _NOW  # type: ignore[misc]
