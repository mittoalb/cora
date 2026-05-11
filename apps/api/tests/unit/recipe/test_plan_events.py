"""Unit tests for the Plan aggregate's event (de)serialization helpers.

Plan event payloads are richer than Method / Practice / Capability
because of the audit snapshots (gate-review Q4): `method_id`,
`method_needs_capabilities_snapshot`, and `asset_capabilities_snapshot`.
These tests pin the deterministic-ordering invariants required for
idempotency-key hashing.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.recipe.aggregates.plan.events import (
    PlanDefined,
    event_type_name,
    from_stored,
    to_payload,
)

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


def _stored(
    event_type: str,
    payload: dict[str, object],
    *,
    stream_id: object | None = None,
) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Plan",
        stream_id=stream_id or uuid4(),  # type: ignore[arg-type]
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


@pytest.mark.unit
def test_event_type_name_returns_class_name() -> None:
    event = PlanDefined(
        plan_id=uuid4(),
        name="X",
        practice_id=uuid4(),
        asset_ids=[],
        method_id=uuid4(),
        method_needs_capabilities_snapshot=[],
        asset_capabilities_snapshot={},
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "PlanDefined"


@pytest.mark.unit
def test_to_payload_serializes_plan_defined_to_primitives() -> None:
    plan_id = uuid4()
    practice_id = uuid4()
    method_id = uuid4()
    asset_id = uuid4()
    cap_id = uuid4()
    event = PlanDefined(
        plan_id=plan_id,
        name="32-ID FlyScan",
        practice_id=practice_id,
        asset_ids=[asset_id],
        method_id=method_id,
        method_needs_capabilities_snapshot=[cap_id],
        asset_capabilities_snapshot={asset_id: [cap_id]},
        occurred_at=_NOW,
    )
    assert to_payload(event) == {
        "plan_id": str(plan_id),
        "name": "32-ID FlyScan",
        "practice_id": str(practice_id),
        "asset_ids": [str(asset_id)],
        "method_id": str(method_id),
        "method_needs_capabilities_snapshot": [str(cap_id)],
        "asset_capabilities_snapshot": {str(asset_id): [str(cap_id)]},
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_to_payload_sorts_asset_ids_for_determinism() -> None:
    """Idempotency-key hashing requires byte-deterministic payloads."""
    a1 = uuid4()
    a2 = uuid4()
    a3 = uuid4()
    forward = PlanDefined(
        plan_id=uuid4(),
        name="X",
        practice_id=uuid4(),
        asset_ids=[a1, a2, a3],
        method_id=uuid4(),
        method_needs_capabilities_snapshot=[],
        asset_capabilities_snapshot={},
        occurred_at=_NOW,
    )
    reverse = PlanDefined(
        plan_id=forward.plan_id,
        name=forward.name,
        practice_id=forward.practice_id,
        asset_ids=[a3, a2, a1],
        method_id=forward.method_id,
        method_needs_capabilities_snapshot=[],
        asset_capabilities_snapshot={},
        occurred_at=_NOW,
    )
    assert to_payload(forward)["asset_ids"] == to_payload(reverse)["asset_ids"]
    assert to_payload(forward)["asset_ids"] == sorted(str(a) for a in [a1, a2, a3])


@pytest.mark.unit
def test_to_payload_sorts_method_needs_capabilities_snapshot_for_determinism() -> None:
    c1 = uuid4()
    c2 = uuid4()
    forward = PlanDefined(
        plan_id=uuid4(),
        name="X",
        practice_id=uuid4(),
        asset_ids=[],
        method_id=uuid4(),
        method_needs_capabilities_snapshot=[c1, c2],
        asset_capabilities_snapshot={},
        occurred_at=_NOW,
    )
    reverse = PlanDefined(
        plan_id=forward.plan_id,
        name=forward.name,
        practice_id=forward.practice_id,
        asset_ids=[],
        method_id=forward.method_id,
        method_needs_capabilities_snapshot=[c2, c1],
        asset_capabilities_snapshot={},
        occurred_at=_NOW,
    )
    assert (
        to_payload(forward)["method_needs_capabilities_snapshot"]
        == to_payload(reverse)["method_needs_capabilities_snapshot"]
    )


@pytest.mark.unit
def test_to_payload_sorts_asset_capabilities_snapshot_keys_and_values() -> None:
    """Both outer dict keys (asset_ids) and inner lists (capability_ids)
    must be deterministically ordered for idempotency-key hashing."""
    a1 = uuid4()
    a2 = uuid4()
    c1 = uuid4()
    c2 = uuid4()
    snapshot_unsorted = {
        a2: [c2, c1],  # outer: a2 first; inner: c2 first
        a1: [c2, c1],
    }
    event = PlanDefined(
        plan_id=uuid4(),
        name="X",
        practice_id=uuid4(),
        asset_ids=[],
        method_id=uuid4(),
        method_needs_capabilities_snapshot=[],
        asset_capabilities_snapshot=snapshot_unsorted,
        occurred_at=_NOW,
    )
    raw = to_payload(event)["asset_capabilities_snapshot"]
    assert isinstance(raw, dict)
    # pyright doesn't narrow the dict's element types from `dict` alone;
    # cast via list[str] for the keys assertion and skip narrowing values.
    keys: list[str] = list(raw.keys())  # pyright: ignore[reportUnknownArgumentType]
    assert keys == sorted([str(a1), str(a2)])
    for caps in raw.values():  # pyright: ignore[reportUnknownVariableType]
        assert caps == sorted([str(c1), str(c2)])


@pytest.mark.unit
def test_from_stored_rebuilds_plan_defined() -> None:
    plan_id = uuid4()
    practice_id = uuid4()
    method_id = uuid4()
    asset_id = uuid4()
    cap_id = uuid4()
    stored = _stored(
        "PlanDefined",
        {
            "plan_id": str(plan_id),
            "name": "32-ID FlyScan",
            "practice_id": str(practice_id),
            "asset_ids": [str(asset_id)],
            "method_id": str(method_id),
            "method_needs_capabilities_snapshot": [str(cap_id)],
            "asset_capabilities_snapshot": {str(asset_id): [str(cap_id)]},
            "occurred_at": _NOW.isoformat(),
        },
    )
    rebuilt = from_stored(stored)
    assert rebuilt == PlanDefined(
        plan_id=plan_id,
        name="32-ID FlyScan",
        practice_id=practice_id,
        asset_ids=[asset_id],
        method_id=method_id,
        method_needs_capabilities_snapshot=[cap_id],
        asset_capabilities_snapshot={asset_id: [cap_id]},
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_to_payload_then_from_stored_round_trips() -> None:
    """Round-trip safety net for the full payload shape including snapshots."""
    asset_id = uuid4()
    cap_id = uuid4()
    original = PlanDefined(
        plan_id=uuid4(),
        name="X",
        practice_id=uuid4(),
        asset_ids=[asset_id],
        method_id=uuid4(),
        method_needs_capabilities_snapshot=[cap_id],
        asset_capabilities_snapshot={asset_id: [cap_id]},
        occurred_at=_NOW,
    )
    stored = _stored("PlanDefined", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    """Foreign event_types in a stream must fail loud, not be silently dropped."""
    stored = _stored("PracticeDefined", {})
    with pytest.raises(ValueError, match="Unknown PlanEvent event_type"):
        from_stored(stored)
