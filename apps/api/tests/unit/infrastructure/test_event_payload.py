"""Unit tests for `cora.infrastructure.deserialize_or_raise`.

Coverage:
  - Successful build returns the constructed event unchanged
  - KeyError / TypeError / AttributeError each become `ValueError`
    tagged `Malformed {event_type} payload`
  - Raw payload is NEVER echoed into the `ValueError` message
    (PII-vault correlation hygiene; see module docstring)
  - Original exception preserved via `__cause__`
  - `extra` widens the catch tuple (covers the 6 quadruple sites
    that wrap inline `Enum(payload[k])` calls)
  - `message_suffix` is placed after `payload` so the architecture
    fitness substring (`Malformed {n} payload`) survives unchanged
  - Exceptions outside the catch tuple propagate unchanged
"""

from dataclasses import dataclass

import pytest

from cora.infrastructure.event_payload import deserialize_or_raise


@dataclass(frozen=True)
class _FooEvent:
    actor_id: str
    count: int


@pytest.mark.unit
def test_deserialize_or_raise_returns_built_event_on_success() -> None:
    result = deserialize_or_raise(
        "FooEvent",
        lambda: _FooEvent(actor_id="a-1", count=2),
    )
    assert result == _FooEvent(actor_id="a-1", count=2)


@pytest.mark.unit
def test_deserialize_or_raise_wraps_key_error_as_value_error() -> None:
    payload: dict[str, str] = {}
    with pytest.raises(ValueError, match="Malformed FooEvent payload"):
        deserialize_or_raise("FooEvent", lambda: _FooEvent(actor_id=payload["missing"], count=0))


@pytest.mark.unit
def test_deserialize_or_raise_wraps_type_error_as_value_error() -> None:
    payload: dict[str, object] = {"actor_id": ["not", "a", "string"]}
    with pytest.raises(ValueError, match="Malformed FooEvent payload"):
        deserialize_or_raise(
            "FooEvent",
            lambda: _FooEvent(actor_id=payload["actor_id"] + 1, count=0),  # type: ignore[operator]
        )


@pytest.mark.unit
def test_deserialize_or_raise_wraps_attribute_error_as_value_error() -> None:
    def builder() -> _FooEvent:
        bogus: object = object()
        return _FooEvent(actor_id=bogus.actor_id, count=1)  # type: ignore[attr-defined]

    with pytest.raises(ValueError, match="Malformed FooEvent payload"):
        deserialize_or_raise("FooEvent", builder)


@pytest.mark.unit
def test_deserialize_or_raise_preserves_original_via_cause() -> None:
    original = KeyError("actor_id")
    with pytest.raises(ValueError) as exc_info:
        deserialize_or_raise("FooEvent", lambda: (_ for _ in ()).throw(original))
    assert exc_info.value.__cause__ is original


@pytest.mark.unit
def test_deserialize_or_raise_does_not_echo_payload_in_message() -> None:
    """Raw payload contents must NOT leak into the ValueError text.
    The fitness test asserts only the `Malformed {n} payload` substring;
    payload values may carry PII-vault correlatable ids that should
    not surface in log aggregators."""
    sensitive = "actor-id-7b3f1a8e-secret"
    payload = {"actor_id": sensitive}
    with pytest.raises(ValueError) as exc_info:
        deserialize_or_raise("FooEvent", lambda: _FooEvent(actor_id=payload["missing"], count=0))
    assert sensitive not in str(exc_info.value)


@pytest.mark.unit
def test_deserialize_or_raise_extra_widens_catch_tuple_for_value_error() -> None:
    """The 6 quadruple sites pass `extra=(ValueError,)` to absorb
    inline `Enum(payload[k])` failures."""
    with pytest.raises(ValueError, match="Malformed FooEvent payload"):
        deserialize_or_raise(
            "FooEvent",
            lambda: (_ for _ in ()).throw(ValueError("bad enum value")),
            extra=(ValueError,),
        )


@pytest.mark.unit
def test_deserialize_or_raise_without_extra_lets_value_error_propagate() -> None:
    """Default empty `extra` must NOT swallow domain ValueErrors raised
    outside the (K/T/A) triple. Mirrors `deserialize_source` in
    `calibration/aggregates/calibration/events.py` which raises a
    typed `InvalidCalibrationSourceError` (a ValueError subclass) that
    must reach callers untransformed."""
    domain_error = ValueError("typed domain failure")
    with pytest.raises(ValueError) as exc_info:
        deserialize_or_raise(
            "FooEvent",
            lambda: (_ for _ in ()).throw(domain_error),
        )
    assert exc_info.value is domain_error


@pytest.mark.unit
def test_deserialize_or_raise_message_suffix_placed_after_payload_token() -> None:
    """The fitness regex matches `Malformed {n} payload` as a literal
    substring. The suffix MUST sit after `payload` so the Actor V1 arm
    can disambiguate without breaking the substring."""
    with pytest.raises(ValueError, match=r"Malformed ActorRegistered payload \(V1\)"):
        deserialize_or_raise(
            "ActorRegistered",
            lambda: (_ for _ in ()).throw(KeyError("actor_id")),
            message_suffix=" (V1)",
        )


@pytest.mark.unit
def test_deserialize_or_raise_propagates_unrelated_exception_types() -> None:
    """Exceptions outside the catch tuple (and outside `extra`) reach
    the caller unchanged. Mirrors `InvalidCalibrationSourceError` raised
    by `deserialize_source` which intentionally bypasses the generic
    wrap."""

    class _DomainError(Exception):
        pass

    with pytest.raises(_DomainError):
        deserialize_or_raise(
            "FooEvent",
            lambda: (_ for _ in ()).throw(_DomainError("domain-specific")),
        )


@pytest.mark.unit
def test_deserialize_or_raise_carries_event_type_into_message() -> None:
    with pytest.raises(ValueError, match="Malformed SomeOtherEvent payload"):
        deserialize_or_raise(
            "SomeOtherEvent",
            lambda: (_ for _ in ()).throw(KeyError("x")),
        )
