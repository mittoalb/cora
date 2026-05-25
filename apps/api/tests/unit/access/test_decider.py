"""Unit tests for the `register_actor` slice's pure decider.

Coverage split: example tests here pin behaviors the PBT can't (whitespace
trimming and empty-name rejection, both excluded by the PBT's strategy
alphabet). Universal claims live in `test_register_actor_decider_properties.py`.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.access.aggregates.actor import InvalidActorNameError
from cora.access.features import register_actor
from cora.access.features.register_actor import RegisterActor

_NOW = datetime(2026, 5, 9, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_decide_validates_name_synchronously_but_drops_it_from_event() -> None:
    new_id = uuid4()
    events = register_actor.decide(
        state=None,
        command=RegisterActor(name="  Doga  "),
        now=_NOW,
        new_id=new_id,
    )
    assert len(events) == 1
    assert events[0].actor_id == new_id


@pytest.mark.unit
def test_decide_rejects_invalid_name() -> None:
    with pytest.raises(InvalidActorNameError):
        register_actor.decide(
            state=None,
            command=RegisterActor(name=""),
            now=_NOW,
            new_id=uuid4(),
        )
