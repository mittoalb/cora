"""Unit tests for shared `cora.infrastructure.channel` types.

`ChannelSchema` + `ChannelFieldSpec` carry the schema declaration on
`<Aggregate>ChannelOpened` event payloads. Round-trip through
to_dict / from_dict is the core invariant — payloads land in jsonb
and need to rebuild faithfully.
"""

import pytest

from cora.infrastructure.channel import ChannelFieldSpec, ChannelSchema


@pytest.mark.unit
def test_field_spec_to_dict_minimal_fields_only() -> None:
    spec = ChannelFieldSpec(type="string")
    assert spec.to_dict() == {"type": "string"}


@pytest.mark.unit
def test_field_spec_to_dict_includes_units_and_description_when_set() -> None:
    spec = ChannelFieldSpec(type="float", units="deg", description="rotation angle")
    assert spec.to_dict() == {
        "type": "float",
        "units": "deg",
        "description": "rotation angle",
    }


@pytest.mark.unit
def test_field_spec_from_dict_round_trips() -> None:
    original = ChannelFieldSpec(type="float", units="C", description="sample temp")
    assert ChannelFieldSpec.from_dict(original.to_dict()) == original


@pytest.mark.unit
def test_field_spec_from_dict_handles_missing_optionals() -> None:
    rebuilt = ChannelFieldSpec.from_dict({"type": "uuid"})
    assert rebuilt == ChannelFieldSpec(type="uuid")


@pytest.mark.unit
def test_schema_default_is_empty_fields() -> None:
    schema = ChannelSchema()
    assert schema.fields == {}
    assert schema.description is None


@pytest.mark.unit
def test_schema_to_dict_excludes_description_when_none() -> None:
    schema = ChannelSchema(fields={"x": ChannelFieldSpec(type="int")})
    assert schema.to_dict() == {"fields": {"x": {"type": "int"}}}


@pytest.mark.unit
def test_schema_to_dict_includes_description_when_set() -> None:
    schema = ChannelSchema(
        fields={"angle": ChannelFieldSpec(type="float", units="deg")},
        description="rotation positions",
    )
    assert schema.to_dict() == {
        "fields": {"angle": {"type": "float", "units": "deg"}},
        "description": "rotation positions",
    }


@pytest.mark.unit
def test_schema_from_dict_round_trips() -> None:
    original = ChannelSchema(
        fields={
            "actor_id": ChannelFieldSpec(type="uuid"),
            "command_name": ChannelFieldSpec(type="string"),
            "decision": ChannelFieldSpec(type="string"),
        },
        description="auth audit log",
    )
    assert ChannelSchema.from_dict(original.to_dict()) == original


@pytest.mark.unit
def test_schema_from_dict_handles_missing_fields_key() -> None:
    """Defensive: a stored schema with no fields rebuilds as empty."""
    rebuilt = ChannelSchema.from_dict({"description": "no columns yet"})
    assert rebuilt.fields == {}
    assert rebuilt.description == "no columns yet"
