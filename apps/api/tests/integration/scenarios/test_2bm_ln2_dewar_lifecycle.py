"""LN2 dewar Supply lifecycle at APS 2-BM.

cluster: Seed
archetype: fsm
bc_primary: Supply
bc_touches: Supply

Scenario test for the Supply BC's full 5-state FSM walk in a
realistic 2-BM operator narrative: a beamline-scope liquid-
nitrogen (LN2) dewar feeds the cooled detector chain across the
beamtime. The operator declares it Available at the start, sees
the dewar level drop below the safe-margin threshold during a
long acquisition session (Degraded), then watches it run dry
(Unavailable), receives a refill (Recovering), and finally
verifies stable pressure before resuming nominal operations
(Available again).

Supply lifecycle operations.

See [[project_pilot_docs_design]] for the phase / file-naming
taxonomy. See [[project_supply_design]] for the FSM design lock
(5-state `Unknown -> Available -> Degraded -> Unavailable ->
Recovering` with manual-acknowledge-only restore back to Available
per the Phoebus latched-alarm convention).

## Why this scenario exists

**First scenario-tier exercise of the Supply BC.** The Supply BC
ships with 6 operator-driven transition slices
covering the full 5-state FSM, but no `test_2bm_*` scenario
exercises it. The facility-install scenario (`test_aps_facility.py`)
seeds an APS-scope LN2 placeholder Supply but never walks it
through the FSM. This scenario is the source-of-truth operator
narrative for "consumable resource exists; it gets used; it
runs low; it runs out; it gets refilled; it returns to nominal".

This scenario exercises 6 of the 8 Supply slices in order:

  - `register_supply` (Unknown genesis; beamline-scope LN2 dewar)
  - `mark_supply_available` (Unknown -> Available; first
    operator observation that the dewar is full + flowing)
  - `degrade_supply` (Available -> Degraded; level below safe-
    margin but still flowing)
  - `mark_supply_unavailable` (Degraded -> Unavailable; dewar
    empty, no flow)
  - `mark_supply_recovering` (Unavailable -> Recovering; refill
    delivered, pressurizing)
  - `restore_supply` (Recovering -> Available; operator
    acknowledges full restoration with explicit gesture, per the
    Phoebus latched-alarm precedent)

## Domain shape (operator narrative)

  1. 2-BM ops registers the cryogenics group's LN2 dewar as a
     beamline-scope Supply at the start of the beamtime.
  2. Operator walks down the dewar, confirms LN2 flowing through
     the detector cold-finger, marks it Available.
  3. ~12 hours into a 24-hour acquisition session, the dewar
     level drops below the 20% safety margin (operator-readable
     LED indicator on the dewar). Operator marks it Degraded
     with the level reading; the detector continues operating
     but the operator schedules an early refill.
  4. Before the refill arrives, the dewar runs dry. Operator
     marks it Unavailable with the timestamp. The detector
     control loop trips to safe state automatically (outside
     CORA's scope); the operator pauses the Run.
  5. Cryogenics group delivers a refill 30 minutes later.
     Operator marks the Supply Recovering with a note about
     the pressurization wait.
  6. After 10 minutes of pressure stability + an operator
     walkdown, the operator restores the Supply to Available
     with the explicit acknowledge gesture. The Run can resume.

## Why a separate scenario

Per [scenarios/README.md](../README.md) Rule 1. The Supply FSM
lifecycle is a fully separable concern from Run / Subject /
Campaign workflows: a Supply can transition independently of
what's running on top of it (it's a "utility / resource" pattern
matching ISA-95 utilities). Bundling with a tomography or
alignment scenario would conflate the two.

The Supply BC does NOT today gate `start_run` or any other
cross-BC slice; it's purely an observability + audit BC
today. (Future: a Supply.Unavailable could be added as
an advisory signal to RunDebriefer or a future RunStartGate.)

## What this scenario surfaces (gap-finding intent)

  - **Supply is observability-only at 10a-b.** No cross-BC
    consumer reads Supply status today. The scenario verifies
    the audit trail (event sequence on the stream) but cannot
    assert any downstream effect. A future scenario would
    couple Supply.Unavailable with a RunDebriefer observation
    or with a Caution registration.
  - **`kind` is free-form.** This scenario uses `"cryogen"` as
    the kind discriminator (matching the seed in
    `test_aps_facility.py`); a real facility might want
    `"cryogen.LN2"` or `"cryogen.helium"` once enough Supply
    types accumulate. Promotion to a closed `SupplyKind` enum
    is deferred-with-trigger per [[project_supply_design]].
  - **The Phoebus latched-alarm convention is load-bearing.**
    `Recovering -> Available` requires an explicit
    `restore_supply` call (operator acknowledgement). A
    `Recovering` Supply does NOT auto-transition even if the
    underlying resource genuinely recovered; the operator
    gesture is the audit signal that says "I have eyeballed
    this and confirmed it works".
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.supply.aggregates.supply import (
    SupplyScope,
    SupplyStatus,
    load_supply,
)
from cora.supply.features.degrade_supply import DegradeSupply
from cora.supply.features.degrade_supply import bind as bind_degrade_supply
from cora.supply.features.mark_supply_available import MarkSupplyAvailable
from cora.supply.features.mark_supply_available import (
    bind as bind_mark_available,
)
from cora.supply.features.mark_supply_recovering import MarkSupplyRecovering
from cora.supply.features.mark_supply_recovering import (
    bind as bind_mark_recovering,
)
from cora.supply.features.mark_supply_unavailable import MarkSupplyUnavailable
from cora.supply.features.mark_supply_unavailable import (
    bind as bind_mark_unavailable,
)
from cora.supply.features.register_supply import RegisterSupply
from cora.supply.features.register_supply import bind as bind_register_supply
from cora.supply.features.restore_supply import RestoreSupply
from cora.supply.features.restore_supply import bind as bind_restore_supply
from tests.integration._helpers import build_postgres_deps
from tests.integration.scenarios._facility_fixture import operator_for

_NOW = datetime(2026, 5, 18, 2, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = operator_for(__file__)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000450bb")

# Scenario tag: 450 (supply ops / LN2 dewar lifecycle).
_SUPPLY_ID = UUID("01900000-0000-7000-8000-000000045001")


def _id_queue() -> list[UUID]:
    """Pre-allocated FixedIdGenerator queue (head-first consumption).

    Supply BC operates standalone (no Subject/Run/Campaign
    dependencies for the FSM walk). This scenario does NOT install
    a facility hierarchy because the Supply.scope = Beamline
    discriminator stands on its own; the cross-aggregate Asset.ref
    pattern (Supply bound to a specific beamline Asset) is
    deferred-with-trigger per [[project_supply_design]].
    """
    e = uuid4
    return [
        # register_supply: supply_id, event_id
        _SUPPLY_ID,
        e(),
        # mark_supply_available: event_id
        e(),
        # degrade_supply: event_id
        e(),
        # mark_supply_unavailable: event_id
        e(),
        # mark_supply_recovering: event_id
        e(),
        # restore_supply: event_id
        e(),
    ]


@pytest.mark.integration
async def test_ln2_dewar_walks_through_all_five_supply_states(
    db_pool: asyncpg.Pool,
) -> None:
    """Register beamline LN2 dewar, walk full FSM (Unknown -> Available
    -> Degraded -> Unavailable -> Recovering -> Available). Assert each
    transition lands on the Supply stream + the final status is back to
    Available."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=_id_queue())

    # ----- register_supply (Unknown genesis) -----

    new_supply_id = await bind_register_supply(deps)(
        RegisterSupply(
            scope=SupplyScope.BEAMLINE,
            kind="cryogen",
            name="2-BM detector LN2 dewar",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert new_supply_id == _SUPPLY_ID

    registered = await load_supply(deps.event_store, _SUPPLY_ID)
    assert registered is not None
    assert registered.status is SupplyStatus.UNKNOWN
    assert registered.scope is SupplyScope.BEAMLINE
    assert registered.kind == "cryogen"

    # ----- Unknown -> Available (operator first-observation) -----

    await bind_mark_available(deps)(
        MarkSupplyAvailable(
            supply_id=_SUPPLY_ID,
            reason=(
                "Operator walkdown at beamtime start; dewar at 95% full, "
                "pressure 2.5 PSI, LN2 flowing through detector cold-finger."
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    available = await load_supply(deps.event_store, _SUPPLY_ID)
    assert available is not None
    assert available.status is SupplyStatus.AVAILABLE

    # ----- Available -> Degraded (level below 20% safety margin) -----

    await bind_degrade_supply(deps)(
        DegradeSupply(
            supply_id=_SUPPLY_ID,
            reason=(
                "Dewar level LED dropped below 20% during a 24-hour "
                "acquisition session at hour ~12; detector still cooling "
                "but operator scheduling early refill."
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    degraded = await load_supply(deps.event_store, _SUPPLY_ID)
    assert degraded is not None
    assert degraded.status is SupplyStatus.DEGRADED

    # ----- Degraded -> Unavailable (dewar ran dry before refill) -----

    await bind_mark_unavailable(deps)(
        MarkSupplyUnavailable(
            supply_id=_SUPPLY_ID,
            reason=(
                "Dewar empty at hour ~15.5; detector cold-finger lost "
                "cooling; control loop tripped to safe state; Run paused "
                "pending refill."
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    unavailable = await load_supply(deps.event_store, _SUPPLY_ID)
    assert unavailable is not None
    assert unavailable.status is SupplyStatus.UNAVAILABLE

    # ----- Unavailable -> Recovering (refill delivered) -----

    await bind_mark_recovering(deps)(
        MarkSupplyRecovering(
            supply_id=_SUPPLY_ID,
            reason=(
                "Cryogenics group delivered refill at hour 16; dewar "
                "filling, pressurizing; awaiting 10 minutes of pressure "
                "stability before confirming."
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    recovering = await load_supply(deps.event_store, _SUPPLY_ID)
    assert recovering is not None
    assert recovering.status is SupplyStatus.RECOVERING

    # ----- Recovering -> Available (operator acknowledges restoration) -----
    # Per Phoebus latched-alarm convention: explicit operator gesture
    # required; no auto-recovery from Recovering.

    await bind_restore_supply(deps)(
        RestoreSupply(
            supply_id=_SUPPLY_ID,
            reason=(
                "Pressure stable at 2.5 PSI for 10+ minutes; LN2 flowing; "
                "operator walkdown confirms detector cold-finger restored. "
                "Run can resume."
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    restored = await load_supply(deps.event_store, _SUPPLY_ID)
    assert restored is not None
    assert restored.status is SupplyStatus.AVAILABLE

    # ----- Assert: Supply stream carries the full FSM walk -----

    supply_events, _supply_version = await deps.event_store.load("Supply", _SUPPLY_ID)
    supply_event_types = [e.event_type for e in supply_events]
    # 6 events covering register + 5 transitions.
    assert supply_event_types == [
        "SupplyRegistered",
        "SupplyMarkedAvailable",
        "SupplyDegraded",
        "SupplyMarkedUnavailable",
        "SupplyMarkedRecovering",
        "SupplyRestored",
    ]

    # ----- Assert: every transition event captures its reason verbatim -----
    # All five transition events carry an operator-supplied `reason`; the
    # one without is the genesis (SupplyRegistered has no reason field).

    transitions_with_reasons = [e for e in supply_events if e.event_type != "SupplyRegistered"]
    for transition_event in transitions_with_reasons:
        assert "reason" in transition_event.payload
        assert len(transition_event.payload["reason"]) > 10  # non-trivial
