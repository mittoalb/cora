"""Pure decider for the `StartRun` command.

Cross-aggregate validation: this is the second decider in the
codebase that takes upstream aggregate state as input (after Plan's
`define_plan`). Per gate-review Q2, the handler pre-loads
Plan + Subject (if subject_id given) + each bound Asset, hands the
loaded entities to this decider as a `RunStartContext`. The decider
treats them as opaque domain data and validates without any I/O.
`now` and `new_id` are injected by the handler from Clock and
IdGenerator ports.

This pattern is the canonical approach for cross-aggregate
validation in CORA going forward (Plan was first, Run is second).
Documented in CONTRIBUTING.md alongside the eventual-consistency
rule.

## Validation order

The decider runs validations in this order; each failure short-
circuits and raises immediately. Order chosen so the most
fundamental issues surface first:

1. State must be None (defensive: stream collision).
   `RunAlreadyExistsError`.
2. Plan must not be Deprecated → `PlanDeprecatedError`.
3. Subject (if non-None) must be in {Mounted, Measured} →
   `SubjectNotMountableError`. Skipped entirely for calibration /
   dark-field runs (where command.subject_id is None and
   context.subject is None).
4. No bound Asset may be Decommissioned → `RunAssetDecommissionedError`
   carrying the offending asset_ids.
5. RE-VALIDATE: `union(asset.families) ⊇ method.needed_families`
   against CURRENT Asset state (gate-review Q5: drift since Plan-bind
   is real; Run-start is the last gate before execution).
   `RunCapabilitiesNotSatisfiedError` carrying the missing capability
   ids. **NOTE**: Method's needed_families comes via Plan; we
   load Plan but NOT Method here — instead, the handler resolved
   Plan → Method at load time and passes the needs as part of...
   wait, re-reading: actually we don't have Method directly in
   RunStartContext. Plan's bind-time snapshot in PlanDefined event
   carries `method_needed_families_snapshot`, but we need
   CURRENT Method state for re-validation. The handler must load
   Method via plan.practice_id → practice.method_id → Method.
   See handler docstring.

   Wait, simpler: we re-load via the snapshot. The PlanDefined
   event captured method_id and the needs snapshot. We could trust
   the snapshot, OR we could re-load Method to get current
   needed_families. Per gate-review Q5 ("re-validate at Run-
   start"), we re-load to catch Method drift too.

   Actually for 6f-1 simplicity, we trust Plan's bind-time
   snapshot for the needs side AND re-validate against current
   Asset capabilities. Method drift between bind and start is a
   secondary concern; if Method's needs change, operators should
   re-bind the Plan. Documented as known gap.

6. Name validation (via `RunName` VO). `InvalidRunNameError`. Last
   because the name is a primitive the operator can fix without
   changing any binding state.

## What's NOT validated

  - Supply availability (Track B Supply BC not shipped). Documented
    as gate-review Q3 known gap.
  - Decision approval (Decision BC not shipped). Documented as
    gate-review Q3 known gap.
  - Subject hazard ⊆ Method clearances (Method's hazardClearances
    facet not shipped). Documented as 6c-deferred enrichment.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from cora.campaign.aggregates.campaign import CampaignStatus
from cora.campaign.aggregates.campaign.events import CampaignRunAdded
from cora.equipment.aggregates.asset import AssetLifecycle
from cora.recipe.aggregates.plan import PlanStatus, validate_wire_endpoints
from cora.run.aggregates.run import (
    CautionAcknowledgement,
    PlanDeprecatedError,
    Run,
    RunAlreadyExistsError,
    RunAssetDecommissionedError,
    RunCannotJoinCampaignError,
    RunCapabilitiesNotSatisfiedError,
    RunClearanceCoverageMismatchError,
    RunName,
    RunRequiresActiveClearanceError,
    RunStarted,
    SubjectNotMountableError,
    validate_effective_parameters_against_method_schema,
    validate_pinned_calibrations,
)
from cora.run.features.start_run.command import StartRun
from cora.run.features.start_run.context import RunStartContext
from cora.subject.aggregates.subject import SubjectStatus

_SUBJECT_RUNNABLE_STATUSES: tuple[SubjectStatus, ...] = (
    SubjectStatus.MOUNTED,
    SubjectStatus.MEASURED,
)

_CAMPAIGN_MEMBERSHIP_ELIGIBLE_STATUSES: tuple[CampaignStatus, ...] = (
    CampaignStatus.PLANNED,
    CampaignStatus.ACTIVE,
    CampaignStatus.HELD,
)


@dataclass(frozen=True)
class RunStartEvents:
    """The events emitted by a successful `start_run` decision.

    Run-side `run_events` is always non-empty (one `RunStarted`).
    Campaign-side `campaign_events` is non-empty only when the command
    supplied `campaign_id`: a single `CampaignRunAdded` mirrors the
    membership write the handler hands to `EventStore.append_streams`.
    Empty otherwise; the handler routes single-stream via `append`.

    Mirrors `amend_clearance`'s `AmendmentEvents`: the decider owns
    cross-aggregate event construction (FCIS), the handler owns I/O
    routing.
    """

    run_events: list[RunStarted]
    campaign_events: list[CampaignRunAdded]


def decide(
    state: Run | None,
    command: StartRun,
    *,
    context: RunStartContext,
    needed_families_snapshot: frozenset[UUID],
    effective_parameters: dict[str, Any],
    method_parameters_schema: dict[str, Any] | None,
    now: datetime,
    new_id: UUID,
) -> RunStartEvents:
    """Decide the events produced by starting a new run.

    `needed_families_snapshot` is the Method's needed_families
    set the handler resolved transitively from `plan.practice_id →
    practice.method_id → method.needed_families`. Passed in as a
    plain frozenset so the decider stays purely state-driven.

    `effective_parameters` is the post-merge dict (Plan defaults +
    command overrides) the handler computed via `merge_patch`.
    `method_parameters_schema` is the Method's parameters_schema
    (None if Method declares no contract). The decider validates
    `effective_parameters` against the schema; STRICT when the schema
    is None — non-empty effective rejected (per audit reversal,
    mirrors the "no Capabilities + non-empty settings → reject"
    anchor). Emits RunStarted carrying BOTH the operator's overrides
    AND the resolved effective set.
    """
    if state is not None:
        raise RunAlreadyExistsError(state.id)

    # cross-BC clearance gate: at least one Safety
    # Clearance must be Active AND reference this Run's scope. The
    # handler pre-loaded every clearance whose bindings reference
    # the Run/Subject/Asset ids via deps.clearance_lookup. Partition
    # on status == "Active" to distinguish "no clearance at all"
    # (RunRequiresActiveClearanceError) from "clearance exists but
    # none Active" (RunClearanceCoverageMismatchError). Modern DDD
    # consensus (Khononov / Dudycz / Herberto Graca 2024-2025): cross-
    # context gating queries a replicated read model (here:
    # proj_safety_clearance_summary), not the upstream aggregate.
    if not context.referencing_clearances:
        raise RunRequiresActiveClearanceError(new_id)
    active_clearances = [c for c in context.referencing_clearances if c.status == "Active"]
    if not active_clearances:
        raise RunClearanceCoverageMismatchError(
            new_id,
            referencing_clearance_count=len(context.referencing_clearances),
        )

    if context.plan.status is PlanStatus.DEPRECATED:
        raise PlanDeprecatedError(context.plan.id)

    if context.subject is not None and context.subject.status not in _SUBJECT_RUNNABLE_STATUSES:
        raise SubjectNotMountableError(
            context.subject.id, current_status=context.subject.status.value
        )

    decommissioned = sorted(
        (
            asset.id
            for asset in context.assets.values()
            if asset.lifecycle is AssetLifecycle.DECOMMISSIONED
        ),
        key=str,
    )
    if decommissioned:
        raise RunAssetDecommissionedError(decommissioned)

    # Re-validation: union of CURRENT bound Asset capabilities must
    # cover Method's needs (per gate-review Q5; drift since Plan-bind
    # is real; Run-start is the last gate).
    union_capabilities: frozenset[UUID] = frozenset(
        cap for asset in context.assets.values() for cap in asset.families
    )
    missing = needed_families_snapshot - union_capabilities
    if missing:
        raise RunCapabilitiesNotSatisfiedError(missing)

    # 6g-c: validate the resolved (defaults + overrides) parameter set
    # against the owning Method's parameters_schema. Strict when the
    # schema is None: non-empty effective parameters are rejected
    # (per audit reversal; mirrors the "no Capabilities + non-
    # empty settings → reject" anchor; see
    # [[project_schema_validated_values_pattern]]).
    validate_effective_parameters_against_method_schema(
        effective_parameters, method_parameters_schema
    )

    # 6h: re-validate every Wire in the Plan's wires set against the
    # CURRENT Asset.ports state (drift since wire-add is real:
    # operators may have removed a referenced port between
    # add_plan_wire and start_run). Mirrors the capability re-validation
    # above. Wires whose endpoint Asset isn't in context.assets surface
    # as PlanWireAssetNotBoundError (the asset was removed from the
    # Plan's binding); wires whose port no longer exists surface as
    # PlanWirePortNotFoundError. See [[project_plan_wiring_design]]
    # §hot-swap procedure for the operational expectation.
    for wire in context.plan.wires:
        validate_wire_endpoints(
            wire,
            bound_asset_ids=context.plan.asset_ids,
            assets_by_id=context.assets,
        )

    # if the caller supplied campaign_id, the handler pre-
    # loaded the Campaign into the context. Verify the Campaign is in a
    # membership-eligible status (Planned / Active / Held); reject
    # terminal Campaigns (Closed / Abandoned) per the design memo
    # membership lock. The handler atomically writes the inverse
    # CampaignRunAdded event to the Campaign stream via
    # EventStore.append_streams.
    if command.campaign_id is not None:
        if context.campaign is None:
            # Defensive: the handler raises CampaignNotFoundError before
            # reaching the decider when the load returns None.
            raise RunCannotJoinCampaignError(
                run_id=new_id,
                campaign_id=command.campaign_id,
                campaign_status="<not found>",
            )
        if context.campaign.status not in _CAMPAIGN_MEMBERSHIP_ELIGIBLE_STATUSES:
            raise RunCannotJoinCampaignError(
                run_id=new_id,
                campaign_id=command.campaign_id,
                campaign_status=context.campaign.status.value,
            )

    name = RunName(command.name)  # validates + trims; raises InvalidRunNameError

    # cardinality cap on the AsShot pin set. NO cross-BC
    # existence check (revision-cited atomic-ID model; eventual-
    # consistency stance per [[project_calibration_design]] anti-hook
    # #3). Mirrors Data BC's register_dataset decider-time treatment
    # for Dataset.used_calibrations exactly.
    pinned_calibrations = validate_pinned_calibrations(command.pinned_calibrations)

    # build the acknowledged_cautions snapshot for the
    # RunStarted event payload. Per the Caution design memo, this
    # snapshot IS the ack (anti-pattern #7: ack lives on the
    # consumption event, never per-operator on the Caution
    # aggregate). NON-BLOCKING (anti-pattern #5): no precondition
    # check is added here; the decider only converts each
    # CautionReference from the context into a CautionAcknowledgement
    # VO and embeds the tuple verbatim.
    acknowledged_cautions = tuple(
        CautionAcknowledgement(
            caution_id=caution.caution_id,
            target_kind=caution.target_kind,
            target_id=caution.target_id,
            category=caution.category,
            severity=caution.severity,
            text_excerpt=caution.text_excerpt,
            workaround_excerpt=caution.workaround_excerpt,
        )
        for caution in context.active_cautions
    )

    run_events: list[RunStarted] = [
        RunStarted(
            run_id=new_id,
            name=name.value,
            plan_id=command.plan_id,
            subject_id=command.subject_id,
            raid=command.raid,
            override_parameters=command.override_parameters,
            effective_parameters=effective_parameters,
            triggered_by=command.triggered_by,
            external_refs=tuple(
                {"scheme": ref.scheme, "id": ref.id} for ref in command.external_refs
            ),
            acknowledged_cautions=acknowledged_cautions,
            campaign_id=command.campaign_id,
            decided_by_decision_id=command.decided_by_decision_id,
            # sort for deterministic byte-form on the event
            # payload (frozenset has no inherent order). The cardinality
            # check ran earlier via validate_pinned_calibrations (12b-5).
            pinned_calibrations=tuple(sorted(pinned_calibrations)),
            occurred_at=now,
        )
    ]

    # FCIS: when campaign_id is set, the decider also emits
    # the inverse `CampaignRunAdded` event for the Campaign stream. The
    # handler hands both lists to `EventStore.append_streams` as a
    # single atomic batch. When campaign_id is None, this list is empty
    # and the handler routes single-stream via `append`.
    campaign_events: list[CampaignRunAdded] = []
    if command.campaign_id is not None:
        campaign_events.append(
            CampaignRunAdded(
                campaign_id=command.campaign_id,
                run_id=new_id,
                occurred_at=now,
            )
        )

    return RunStartEvents(run_events=run_events, campaign_events=campaign_events)
