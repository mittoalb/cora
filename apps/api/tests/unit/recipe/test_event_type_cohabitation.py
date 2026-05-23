"""Smoke test: Recipe Capability + Method + Operation Procedure
event types coexist in a single event store without their
`event_type` discriminators tangling.

Recipe Capability events were renamed from `CapabilityDefined` to
`RecipeCapabilityDefined` to avoid collision with Equipment Family's
legacy dual-match arm (which still accepts the legacy
`"CapabilityDefined"` event type for older streams). This test pins
that the three aggregate event-type namespaces stay distinct:

  - Equipment Family: `FamilyDefined` (legacy `CapabilityDefined`
    accepted via dual-match in Family.from_stored)
  - Recipe Capability: `RecipeCapabilityDefined` (NOT collision-prone)
  - Recipe Method: `MethodDefined`
  - Operation Procedure: `ProcedureRegistered`

A regression that re-flattens any of these (e.g. dropping the
`Recipe` prefix from the Capability event types) would silently
route Recipe Capability events into Equipment Family's evolver
and corrupt fold-on-read. This smoke test catches that by writing
all four event types to the same in-memory event store and
asserting each stream folds to the right aggregate type with the
right payload — no cross-contamination.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.family import FamilyDefined
from cora.equipment.aggregates.family import event_type_name as family_event_type_name
from cora.equipment.aggregates.family import from_stored as family_from_stored
from cora.equipment.aggregates.family import to_payload as family_to_payload
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.operation.aggregates.procedure import ProcedureRegistered
from cora.operation.aggregates.procedure import event_type_name as procedure_event_type_name
from cora.operation.aggregates.procedure import from_stored as procedure_from_stored
from cora.operation.aggregates.procedure import to_payload as procedure_to_payload
from cora.recipe.aggregates.capability import (
    Capability,
    CapabilityCode,
    CapabilityName,
    ExecutorShape,
    RecipeCapabilityDefined,
)
from cora.recipe.aggregates.capability import (
    event_type_name as capability_event_type_name,
)
from cora.recipe.aggregates.capability import to_payload as capability_to_payload
from cora.recipe.aggregates.method import MethodDefined
from cora.recipe.aggregates.method import event_type_name as method_event_type_name
from cora.recipe.aggregates.method import from_stored as method_from_stored
from cora.recipe.aggregates.method import to_payload as method_to_payload

_NOW = datetime(2026, 5, 18, 12, 0, 0, tzinfo=UTC)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")


async def _append(
    store: InMemoryEventStore,
    *,
    stream_type: str,
    stream_id: UUID,
    event_type: str,
    payload: dict[str, object],
) -> None:
    """Lift one domain event into a NewEvent and append."""
    await store.append(
        stream_type=stream_type,
        stream_id=stream_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type,
                payload=payload,
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name=f"Define{stream_type}",
                correlation_id=_CORRELATION_ID,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )


@pytest.mark.unit
async def test_recipe_capability_method_procedure_events_coexist_on_replay() -> None:
    """All four aggregate types' genesis events live in the same store
    without `from_stored` cross-contamination. Pinned because Capability
    events are explicitly renamed to RecipeCapability* to avoid this
    collision; a regression that drops the prefix would route Recipe
    Capability events into Equipment Family's evolver."""
    store = InMemoryEventStore()

    # Recipe Capability
    capability_id = uuid4()
    cap_event = RecipeCapabilityDefined(
        capability_id=capability_id,
        code=CapabilityCode("cora.capability.cohabit").value,
        name=CapabilityName("CohabitCapability").value,
        required_affordances=frozenset(),
        executor_shapes=frozenset({ExecutorShape.METHOD, ExecutorShape.PROCEDURE}),
        occurred_at=_NOW,
    )
    await _append(
        store,
        stream_type="Capability",
        stream_id=capability_id,
        event_type=capability_event_type_name(cap_event),
        payload=capability_to_payload(cap_event),
    )

    # Equipment Family (different BC, same event store)
    family_id = uuid4()
    family_event = FamilyDefined(
        family_id=family_id,
        name="CohabitFamily",
        occurred_at=_NOW,
    )
    await _append(
        store,
        stream_type="Family",
        stream_id=family_id,
        event_type=family_event_type_name(family_event),
        payload=family_to_payload(family_event),
    )

    # Recipe Method (bound to the Capability above)
    method_id = uuid4()
    method_event = MethodDefined(
        method_id=method_id,
        name="CohabitMethod",
        needed_families=(family_id,),
        capability_id=capability_id,
        occurred_at=_NOW,
    )
    await _append(
        store,
        stream_type="Method",
        stream_id=method_id,
        event_type=method_event_type_name(method_event),
        payload=method_to_payload(method_event),
    )

    # Operation Procedure (bound to the same Capability)
    procedure_id = uuid4()
    procedure_event = ProcedureRegistered(
        procedure_id=procedure_id,
        name="CohabitProcedure",
        kind="alignment",
        target_asset_ids=(),
        parent_run_id=None,
        capability_id=capability_id,
        occurred_at=_NOW,
    )
    await _append(
        store,
        stream_type="Procedure",
        stream_id=procedure_id,
        event_type=procedure_event_type_name(procedure_event),
        payload=procedure_to_payload(procedure_event),
    )

    # Each from_stored routes its own stream's events to the right
    # aggregate type. No discriminator collision means each stream
    # rebuilds with the right payload shape + capability_id linkage.
    from cora.recipe.aggregates.capability import (
        fold as capability_fold,
    )
    from cora.recipe.aggregates.capability import (
        from_stored as capability_from_stored,
    )

    cap_stored, _ = await store.load("Capability", capability_id)
    rebuilt_cap = capability_fold([capability_from_stored(s) for s in cap_stored])
    assert isinstance(rebuilt_cap, Capability)
    assert rebuilt_cap.id == capability_id

    family_stored, _ = await store.load("Family", family_id)
    rebuilt_family = family_from_stored(family_stored[0])
    assert isinstance(rebuilt_family, FamilyDefined)
    assert rebuilt_family.family_id == family_id

    method_stored, _ = await store.load("Method", method_id)
    rebuilt_method = method_from_stored(method_stored[0])
    assert isinstance(rebuilt_method, MethodDefined)
    assert rebuilt_method.method_id == method_id
    assert rebuilt_method.capability_id == capability_id

    procedure_stored, _ = await store.load("Procedure", procedure_id)
    rebuilt_procedure = procedure_from_stored(procedure_stored[0])
    assert isinstance(rebuilt_procedure, ProcedureRegistered)
    assert rebuilt_procedure.procedure_id == procedure_id
    assert rebuilt_procedure.capability_id == capability_id
