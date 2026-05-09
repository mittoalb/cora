"""ActorName value-object validation."""

import pytest

from cora.access.domain.actor import ActorName, InvalidActorNameError


@pytest.mark.unit
def test_actor_name_accepts_normal_string() -> None:
    name = ActorName("Doga")
    assert name.value == "Doga"


@pytest.mark.unit
def test_actor_name_trims_whitespace() -> None:
    name = ActorName("  Doga  ")
    assert name.value == "Doga"


@pytest.mark.unit
def test_actor_name_rejects_empty_string() -> None:
    with pytest.raises(InvalidActorNameError):
        ActorName("")


@pytest.mark.unit
def test_actor_name_rejects_whitespace_only() -> None:
    with pytest.raises(InvalidActorNameError):
        ActorName("   \t\n   ")


@pytest.mark.unit
def test_actor_name_rejects_too_long() -> None:
    with pytest.raises(InvalidActorNameError):
        ActorName("a" * 201)


@pytest.mark.unit
def test_actor_name_accepts_max_length() -> None:
    name = ActorName("a" * 200)
    assert len(name.value) == 200


@pytest.mark.unit
def test_actor_name_is_frozen() -> None:
    name = ActorName("Doga")
    with pytest.raises(AttributeError):
        name.value = "Other"  # type: ignore[misc]
