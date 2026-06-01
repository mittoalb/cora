"""Property-based tests for `register_mount.decide` (Equipment BC).

Mirrors the Access / Trust decider-PBT pattern on an Equipment BC
create-style command with a `context` cross-aggregate kwarg.
Universal claims across generated inputs:

  - state=None + context.existing_mount_id=None + valid command
    emits a single MountRegistered with the injected ids / now
    and SlotCode-trimmed slot_code.
  - state=Mount always raises MountAlreadyExistsError, carrying the
    pre-existing mount_id.
  - state=None + context.existing_mount_id set always raises
    MountAlreadyExistsError, carrying the context mount_id (slot-
    code collision).
  - Pure: same (state, command, context, now, new_id) returns the
    same events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.equipment.aggregates._drawing import Drawing, DrawingSystem
from cora.equipment.aggregates._placement import (
    Placement,
    ReferenceSurface,
    UnitSystem,
)
from cora.equipment.aggregates.mount import (
    SLOT_CODE_MAX_LENGTH,
    Mount,
    MountAlreadyExistsError,
    MountRegistered,
    MountStatus,
)
from cora.equipment.aggregates.mount.state import SlotCode
from cora.equipment.features import register_mount
from cora.equipment.features.register_mount import RegisterMount, RegisterMountContext
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_SLOT_CODE = printable_ascii_text(min_size=1, max_size=SLOT_CODE_MAX_LENGTH)
_DRAWING_NUMBER = printable_ascii_text(min_size=1, max_size=64)


def _placement(parent_frame_id: UUID) -> Placement:
    return Placement(
        x=0.0,
        y=0.0,
        z=259313.0,
        rx=0.0,
        ry=0.0,
        rz=0.0,
        parent_frame_id=parent_frame_id,
        reference_surface=ReferenceSurface.SHIELDING_FACE,
        tol_x=0.25,
        tol_y=0.25,
        tol_z=5.0,
        tol_rx=0.0,
        tol_ry=0.0,
        tol_rz=0.0,
        units=UnitSystem.SI_MM_RAD,
    )


def _mount(mount_id: UUID, frame_id: UUID) -> Mount:
    return Mount(
        id=mount_id,
        slot_code=SlotCode("existing"),
        parent_mount_id=None,
        placement=_placement(frame_id),
        drawing=None,
        installed_asset_id=None,
        status=MountStatus.ACTIVE,
    )


@pytest.mark.unit
@given(
    slot_code=_SLOT_CODE,
    parent_mount_id=st.one_of(st.none(), st.uuids()),
    drawing_number=_DRAWING_NUMBER,
    include_drawing=st.booleans(),
    frame_id=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_mount_emits_exactly_one_event_with_injected_fields(
    slot_code: str,
    parent_mount_id: UUID | None,
    drawing_number: str,
    include_drawing: bool,
    frame_id: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    """Empty stream + free slot + valid command -> single MountRegistered."""
    placement = _placement(frame_id)
    drawing = (
        Drawing(system=DrawingSystem.ICMS, number=drawing_number, revision=None)
        if include_drawing
        else None
    )
    command = RegisterMount(
        slot_code=slot_code,
        parent_mount_id=parent_mount_id,
        placement=placement,
        drawing=drawing,
    )
    events = register_mount.decide(
        state=None,
        command=command,
        context=RegisterMountContext(existing_mount_id=None),
        now=now,
        new_id=new_id,
    )
    assert events == [
        MountRegistered(
            mount_id=new_id,
            slot_code=slot_code,
            parent_mount_id=parent_mount_id,
            placement=placement,
            drawing=drawing,
            occurred_at=now,
        )
    ]


@pytest.mark.unit
@given(
    existing_id=st.uuids(),
    slot_code=_SLOT_CODE,
    frame_id=st.uuids(),
    parent_mount_id=st.one_of(st.none(), st.uuids()),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_mount_on_existing_state_always_raises_already_exists(
    existing_id: UUID,
    slot_code: str,
    frame_id: UUID,
    parent_mount_id: UUID | None,
    now: datetime,
    new_id: UUID,
) -> None:
    """Any non-None state -> MountAlreadyExistsError carrying state.id."""
    command = RegisterMount(
        slot_code=slot_code,
        parent_mount_id=parent_mount_id,
        placement=_placement(frame_id),
        drawing=None,
    )
    with pytest.raises(MountAlreadyExistsError) as exc:
        register_mount.decide(
            state=_mount(existing_id, frame_id),
            command=command,
            context=RegisterMountContext(existing_mount_id=None),
            now=now,
            new_id=new_id,
        )
    assert exc.value.mount_id == existing_id


@pytest.mark.unit
@given(
    colliding_id=st.uuids(),
    slot_code=_SLOT_CODE,
    frame_id=st.uuids(),
    parent_mount_id=st.one_of(st.none(), st.uuids()),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_mount_with_slot_code_collision_always_raises_already_exists(
    colliding_id: UUID,
    slot_code: str,
    frame_id: UUID,
    parent_mount_id: UUID | None,
    now: datetime,
    new_id: UUID,
) -> None:
    """context.existing_mount_id set -> MountAlreadyExistsError carrying context id."""
    command = RegisterMount(
        slot_code=slot_code,
        parent_mount_id=parent_mount_id,
        placement=_placement(frame_id),
        drawing=None,
    )
    with pytest.raises(MountAlreadyExistsError) as exc:
        register_mount.decide(
            state=None,
            command=command,
            context=RegisterMountContext(existing_mount_id=colliding_id),
            now=now,
            new_id=new_id,
        )
    assert exc.value.mount_id == colliding_id


@pytest.mark.unit
@given(
    slot_code=_SLOT_CODE,
    parent_mount_id=st.one_of(st.none(), st.uuids()),
    frame_id=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_register_mount_is_pure_same_input_same_output(
    slot_code: str,
    parent_mount_id: UUID | None,
    frame_id: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    """Two calls with identical args return identical events (no clock leakage)."""
    command = RegisterMount(
        slot_code=slot_code,
        parent_mount_id=parent_mount_id,
        placement=_placement(frame_id),
        drawing=None,
    )
    context = RegisterMountContext(existing_mount_id=None)
    first = register_mount.decide(
        state=None, command=command, context=context, now=now, new_id=new_id
    )
    second = register_mount.decide(
        state=None, command=command, context=context, new_id=new_id, now=now
    )
    assert first == second
