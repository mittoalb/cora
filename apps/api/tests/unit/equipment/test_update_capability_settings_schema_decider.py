"""Unit tests for the `update_capability_settings_schema` slice's pure decider.

Phase 5g-a. The decider:
  - Raises CapabilityNotFoundError on empty state
  - Validates the proposed schema via validate_settings_schema
  - No-ops (returns []) on unchanged-vs-current schema
  - Emits CapabilitySettingsSchemaUpdated otherwise

Schema can be set, replaced, or cleared (None payload). All
lifecycle states (Defined / Versioned / Deprecated) are valid
sources — schema iteration is independent of content lifecycle.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from cora.equipment.aggregates.capability import (
    Capability,
    CapabilityName,
    CapabilityNotFoundError,
    CapabilitySettingsSchemaUpdated,
    CapabilityStatus,
    InvalidCapabilitySettingsSchemaError,
)
from cora.equipment.features import update_capability_settings_schema
from cora.equipment.features.update_capability_settings_schema import UpdateCapabilitySettingsSchema

_NOW = datetime(2026, 5, 13, 12, 0, 0, tzinfo=UTC)
_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _capability(
    *,
    status: CapabilityStatus = CapabilityStatus.DEFINED,
    settings_schema: dict[str, Any] | None = None,
) -> Capability:
    return Capability(
        id=uuid4(),
        name=CapabilityName("Tomography"),
        status=status,
        settings_schema=settings_schema,
    )


def _valid_schema(min_val: int = 5) -> dict[str, Any]:
    return {
        "$schema": _DRAFT,
        "type": "object",
        "properties": {"energy_kev": {"type": "number", "minimum": min_val}},
    }


@pytest.mark.unit
def test_decide_emits_event_when_setting_schema_for_first_time() -> None:
    state = _capability(settings_schema=None)
    schema = _valid_schema()
    events = update_capability_settings_schema.decide(
        state=state,
        command=UpdateCapabilitySettingsSchema(capability_id=state.id, settings_schema=schema),
        now=_NOW,
    )
    assert events == [
        CapabilitySettingsSchemaUpdated(
            capability_id=state.id,
            settings_schema=schema,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_emits_event_when_replacing_schema() -> None:
    state = _capability(settings_schema=_valid_schema(min_val=5))
    new_schema = _valid_schema(min_val=10)
    events = update_capability_settings_schema.decide(
        state=state,
        command=UpdateCapabilitySettingsSchema(capability_id=state.id, settings_schema=new_schema),
        now=_NOW,
    )
    assert len(events) == 1
    assert events[0].settings_schema == new_schema


@pytest.mark.unit
def test_decide_emits_event_when_clearing_schema() -> None:
    """Clearing via None payload IS an event (audit trail of
    'operator removed declarations on date X')."""
    state = _capability(settings_schema=_valid_schema())
    events = update_capability_settings_schema.decide(
        state=state,
        command=UpdateCapabilitySettingsSchema(capability_id=state.id, settings_schema=None),
        now=_NOW,
    )
    assert len(events) == 1
    assert events[0].settings_schema is None


@pytest.mark.unit
def test_decide_no_op_when_schema_unchanged() -> None:
    """Re-submitting the same schema is a no-op (no event emitted).
    Avoids audit-log noise; the value IS the audit, identical
    re-submission carries no information."""
    schema = _valid_schema()
    state = _capability(settings_schema=schema)
    events = update_capability_settings_schema.decide(
        state=state,
        command=UpdateCapabilitySettingsSchema(capability_id=state.id, settings_schema=schema),
        now=_NOW,
    )
    assert events == []


@pytest.mark.unit
def test_decide_no_op_when_both_current_and_proposed_are_none() -> None:
    state = _capability(settings_schema=None)
    events = update_capability_settings_schema.decide(
        state=state,
        command=UpdateCapabilitySettingsSchema(capability_id=state.id, settings_schema=None),
        now=_NOW,
    )
    assert events == []


@pytest.mark.unit
def test_decide_raises_capability_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(CapabilityNotFoundError) as exc_info:
        update_capability_settings_schema.decide(
            state=None,
            command=UpdateCapabilitySettingsSchema(
                capability_id=target_id, settings_schema=_valid_schema()
            ),
            now=_NOW,
        )
    assert exc_info.value.capability_id == target_id


@pytest.mark.unit
def test_decide_raises_invalid_schema_for_missing_dollar_schema() -> None:
    state = _capability()
    with pytest.raises(InvalidCapabilitySettingsSchemaError):
        update_capability_settings_schema.decide(
            state=state,
            command=UpdateCapabilitySettingsSchema(
                capability_id=state.id,
                settings_schema={"type": "object"},  # no $schema
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_raises_invalid_schema_for_forbidden_keyword() -> None:
    state = _capability()
    with pytest.raises(InvalidCapabilitySettingsSchemaError):
        update_capability_settings_schema.decide(
            state=state,
            command=UpdateCapabilitySettingsSchema(
                capability_id=state.id,
                settings_schema={"$schema": _DRAFT, "oneOf": [{"type": "string"}]},
            ),
            now=_NOW,
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "lifecycle_status",
    [CapabilityStatus.DEFINED, CapabilityStatus.VERSIONED, CapabilityStatus.DEPRECATED],
)
def test_decide_accepts_schema_update_in_any_lifecycle_state(
    lifecycle_status: CapabilityStatus,
) -> None:
    """Schema iteration is independent of content lifecycle: schema
    can be updated even on Deprecated capabilities (operators may
    refine the audit-record schema after deprecation)."""
    state = _capability(status=lifecycle_status)
    events = update_capability_settings_schema.decide(
        state=state,
        command=UpdateCapabilitySettingsSchema(
            capability_id=state.id, settings_schema=_valid_schema()
        ),
        now=_NOW,
    )
    assert len(events) == 1
