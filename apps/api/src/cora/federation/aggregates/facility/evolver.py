"""Evolver: replay events to reconstruct Facility state.

Two-event stream per the locked design:

  - `FacilityRegistered`: genesis. status set to ACTIVE.
    Folds `occurred_at` -> `registered_at` and `registered_by` denorm
    per [[project_fold_symmetry_design]] genesis pair.
  - `FacilityDecommissioned`: terminal. status set to DECOMMISSIONED.
    Folds `occurred_at` -> `decommissioned_at` and `decommissioned_by`
    denorm per fold-symmetry terminal-transition pair.

Source-state guards live at the decider, NOT here; the evolver trusts
the event log (folded events have already passed their decider). The
terminal `assert_never` case forces pyright (and the runtime) to error
if a new event type is added to `FacilityEvent` without a matching
match arm here.

Transition events applied to empty state raise `ValueError` via the
shared `require_state` helper at `cora.infrastructure.evolver`.
"""

from collections.abc import Sequence
from dataclasses import replace
from typing import assert_never

from cora.federation.aggregates.facility.events import (
    FacilityDecommissioned,
    FacilityEvent,
    FacilityRegistered,
    FacilityTrustAnchorCredentialAdded,
    FacilityTrustAnchorCredentialRemoved,
)
from cora.federation.aggregates.facility.state import (
    Facility,
    FacilityName,
    FacilityStatus,
)
from cora.infrastructure.evolver import require_state


def evolve(state: Facility | None, event: FacilityEvent) -> Facility:
    """Apply one event to the current state."""
    match event:
        case FacilityRegistered(
            facility_id=facility_id,
            code=code,
            display_name=display_name,
            kind=kind,
            parent_id=parent_id,
            alternate_identifiers=alternate_identifiers,
            registered_by=registered_by,
            occurred_at=occurred_at,
        ):
            _ = state  # FacilityRegistered is the genesis event; prior state ignored
            return Facility(
                id=facility_id,
                code=code,
                display_name=FacilityName(display_name),
                kind=kind,
                parent_id=parent_id,
                trust_anchor_credential_ids=frozenset(),
                status=FacilityStatus.ACTIVE,
                persistent_id=None,
                alternate_identifiers=alternate_identifiers,
                registered_at=occurred_at,
                registered_by=registered_by,
                decommissioned_at=None,
                decommissioned_by=None,
            )
        case FacilityDecommissioned(
            decommissioned_by=decommissioned_by,
            occurred_at=occurred_at,
        ):
            prior = require_state(state, "FacilityDecommissioned")
            return replace(
                prior,
                status=FacilityStatus.DECOMMISSIONED,
                decommissioned_at=occurred_at,
                decommissioned_by=decommissioned_by,
            )
        case FacilityTrustAnchorCredentialAdded(
            credential_id=credential_id,
        ):
            prior = require_state(state, "FacilityTrustAnchorCredentialAdded")
            return replace(
                prior,
                trust_anchor_credential_ids=prior.trust_anchor_credential_ids | {credential_id},
            )
        case FacilityTrustAnchorCredentialRemoved(
            credential_id=credential_id,
        ):
            prior = require_state(state, "FacilityTrustAnchorCredentialRemoved")
            return replace(
                prior,
                trust_anchor_credential_ids=prior.trust_anchor_credential_ids - {credential_id},
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[FacilityEvent]) -> Facility | None:
    """Replay a stream of events from the empty initial state."""
    state: Facility | None = None
    for event in events:
        state = evolve(state, event)
    return state
