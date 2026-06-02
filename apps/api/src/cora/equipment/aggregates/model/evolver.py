"""Evolver: replay events to reconstruct Model state.

Status mapping per event type:
  - `ModelDefined`        -> DEFINED   (genesis; version=None unless
                                        ModelDefined.version_tag was set)
  - `ModelVersioned`      -> VERSIONED (version=event.version_tag;
                                        multi-source: Defined | Versioned;
                                        replaces name, manufacturer,
                                        part_number, declared_family_ids)
  - `ModelDeprecated`     -> DEPRECATED (everything else preserved;
                                         multi-source: Defined | Versioned)
  - `ModelFamilyAdded`    -> status preserved; declared_family_ids
                             gains family_id (targeted mutation)
  - `ModelFamilyRemoved`  -> status preserved; declared_family_ids
                             loses family_id

The mapping is hardcoded per match arm; the event type IS the
state-change indicator (no status field in event payloads).

Transition events applied to empty state raise via `require_state`.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.equipment.aggregates.model.events import (
    ModelDefined,
    ModelDeprecated,
    ModelEvent,
    ModelFamilyAdded,
    ModelFamilyRemoved,
    ModelVersioned,
)
from cora.equipment.aggregates.model.state import (
    Model,
    ModelName,
    ModelStatus,
    PartNumber,
)
from cora.infrastructure.evolver import require_state


def evolve(state: Model | None, event: ModelEvent) -> Model:
    """Apply one event to the current state."""
    match event:
        case ModelDefined(
            model_id=model_id,
            name=name,
            manufacturer=manufacturer,
            part_number=part_number,
            declared_family_ids=declared_family_ids,
            version_tag=version_tag,
        ):
            _ = state  # ModelDefined is the genesis event; prior state ignored
            return Model(
                id=model_id,
                name=ModelName(name),
                manufacturer=manufacturer,
                part_number=PartNumber(part_number),
                declared_family_ids=declared_family_ids,
                status=ModelStatus.DEFINED,
                version=version_tag,
            )
        case ModelVersioned(
            name=name,
            manufacturer=manufacturer,
            part_number=part_number,
            declared_family_ids=declared_family_ids,
            version_tag=version_tag,
        ):
            prior = require_state(state, "ModelVersioned")
            return Model(
                id=prior.id,
                # Wholesale replacement (a new version IS a new declaration).
                name=ModelName(name),
                manufacturer=manufacturer,
                part_number=PartNumber(part_number),
                declared_family_ids=declared_family_ids,
                status=ModelStatus.VERSIONED,
                version=version_tag,
            )
        case ModelDeprecated():
            prior = require_state(state, "ModelDeprecated")
            return Model(
                id=prior.id,
                name=prior.name,
                manufacturer=prior.manufacturer,
                part_number=prior.part_number,
                # declared_family_ids PRESERVED across deprecation; the
                # historical declaration stays visible for audit.
                declared_family_ids=prior.declared_family_ids,
                status=ModelStatus.DEPRECATED,
                version=prior.version,
            )
        case ModelFamilyAdded(family_id=family_id):
            prior = require_state(state, "ModelFamilyAdded")
            return Model(
                id=prior.id,
                name=prior.name,
                manufacturer=prior.manufacturer,
                part_number=prior.part_number,
                declared_family_ids=prior.declared_family_ids | {family_id},
                # Status preserved across targeted mutation.
                status=prior.status,
                version=prior.version,
            )
        case ModelFamilyRemoved(family_id=family_id):
            prior = require_state(state, "ModelFamilyRemoved")
            return Model(
                id=prior.id,
                name=prior.name,
                manufacturer=prior.manufacturer,
                part_number=prior.part_number,
                declared_family_ids=prior.declared_family_ids - {family_id},
                status=prior.status,
                version=prior.version,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[ModelEvent]) -> Model | None:
    """Replay a stream of events from the empty initial state."""
    state: Model | None = None
    for event in events:
        state = evolve(state, event)
    return state
