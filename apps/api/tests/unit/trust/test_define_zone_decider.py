"""Unit tests for the `define_zone` slice's pure decider.

Coverage split: example tests here pin behaviors the PBT can't (whitespace
trimming via ZoneName value object, and empty-name rejection, both excluded
by the PBT's strategy alphabet). Universal claims live in
`test_define_zone_decider_properties.py`.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.trust.aggregates.zone import InvalidZoneNameError
from cora.trust.features import define_zone
from cora.trust.features.define_zone import DefineZone

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_decide_trims_name_via_value_object() -> None:
    new_id = uuid4()
    events = define_zone.decide(
        state=None,
        command=DefineZone(name="  Detector  "),
        now=_NOW,
        new_id=new_id,
    )
    assert events[0].name == "Detector"


@pytest.mark.unit
def test_decide_rejects_invalid_name() -> None:
    with pytest.raises(InvalidZoneNameError):
        define_zone.decide(
            state=None,
            command=DefineZone(name=""),
            now=_NOW,
            new_id=uuid4(),
        )
