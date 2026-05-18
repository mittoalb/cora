"""Evolver: replay events to reconstruct Run state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `RunEvent` without a matching match arm here.

Status mapping per event type:
  - `RunStarted`            -> RUNNING   (genesis; the start-event puts the
                                          Run into the active steady-state)
  - `RunHeld`               -> HELD      (pause)
  - `RunResumed`            -> RUNNING   (un-pause; back to the active steady-state)
  - `RunCompleted`          -> COMPLETED (happy-path terminal)
  - `RunAborted`            -> ABORTED   (emergency-exit terminal)
  - `RunStopped`            -> STOPPED   (controlled-exit terminal)
  - `RunTruncated`          -> TRUNCATED (partial-data terminal)
  - `RunAdjusted`           -> status preserved; mutates effective_parameters
                                          + last_adjusted_at + adjustment_count
                                          (Phase 6j)
  - `RunCampaignAssigned`   -> status preserved; sets campaign_id (Phase 6i-c)
  - `RunCampaignUnassigned` -> status preserved; clears campaign_id (Phase 6i-c)

The mapping is hardcoded per match arm — the event type IS the
state-change indicator (no status field in event payloads). Same
precedent as `PlanDefined → DEFINED` / `PlanVersioned → VERSIONED` /
`PlanDeprecated → DEPRECATED` / `SubjectMounted → MOUNTED`.

Hold ⇄ Resume is the first bidirectional cycle in any Run aggregate
event stream. The fold is order-sensitive (replay is sequential) so
[RunHeld, RunResumed, RunHeld, RunResumed, RunCompleted] correctly
yields COMPLETED. Per-cycle audit lives in the event stream itself;
the aggregate state only carries the latest status (slim-aggregate
principle, gate-review 6f-3 L9 lock).

**Critical invariant**: every transition arm MUST carry `id`,
`name`, `plan_id`, `subject_id`, `raid`, `override_parameters`,
`effective_parameters`, `triggered_by`, `reading_logbook_id`,
`external_refs`, `campaign_id`, `last_adjusted_at`, AND
`adjustment_count` through from prior state.
Constructing `Run(id=..., name=..., plan_id=..., subject_id=...,
status=...)` without explicitly passing the additive fields would
silently WIPE them to defaults (empty dict / None / empty frozenset
/ 0). Pinned by the per-transition preserve-fields tests.

`reading_logbook_id` (Phase 6f-5b) is set by the
`RunReadingLogbookOpened` arm (lazy open-on-first-write triggered
by `append_run_reading`); all other arms preserve whatever prior
state held. Pre-6f-5b streams fold with `reading_logbook_id=None`.

`campaign_id` (Phase 6i-c) is set at genesis from `RunStarted.
campaign_id` (None when StartRun.campaign_id was not provided), set
to `event.campaign_id` by the `RunCampaignAssigned` arm, and cleared
to None by the `RunCampaignUnassigned` arm. All other arms preserve
prior state's campaign_id (membership survives lifecycle transitions
like running → held → completed). Pre-6i-c streams fold with
`campaign_id=None` (forward-compat via payload.get in from_stored).

`last_adjusted_at` and `adjustment_count` (Phase 6j) start at None / 0
at genesis. The `RunAdjusted` arm replaces `effective_parameters`,
stamps `last_adjusted_at = event.occurred_at`, and increments
`adjustment_count`. All other arms preserve prior state's values:
mid-flight adjustments survive Hold ⇄ Resume cycles and the terminal
transitions stamp the closing effective set (the last value steered
before the Run ended). Pre-6j streams fold with the safe defaults.

This evolver previously used `dataclasses.replace(state,
status=...)` for the transition arms (terse, but no field-add
review surface — new fields would silently carry through without
prompting evolver-arm review). Aligned to explicit construction
post-domain-audit to match the documented pattern in
Asset/Plan/Method/Practice/Family/Subject evolvers.

Transition events applied to empty state raise ValueError: they
can never appear before `RunStarted` in a well-formed stream. The
`require_state` helper at `cora.infrastructure.evolver` keeps
per-arm bodies short (hoisted post-7e once the 11th identical
copy landed).
"""

from collections.abc import Sequence
from typing import assert_never

from cora.infrastructure.evolver import require_state
from cora.run.aggregates.run.events import (
    RunAborted,
    RunAdjusted,
    RunCampaignAssigned,
    RunCampaignUnassigned,
    RunCompleted,
    RunEvent,
    RunHeld,
    RunReadingLogbookOpened,
    RunResumed,
    RunStarted,
    RunStopped,
    RunTruncated,
)
from cora.run.aggregates.run.state import ExternalRef, Run, RunName, RunStatus


def evolve(state: Run | None, event: RunEvent) -> Run:
    """Apply one event to the current state."""
    match event:
        case RunStarted(
            run_id=run_id,
            name=name,
            plan_id=plan_id,
            subject_id=subject_id,
            raid=raid,
            override_parameters=override_parameters,
            effective_parameters=effective_parameters,
            triggered_by=triggered_by,
            external_refs=external_refs,
            campaign_id=campaign_id,
            calibration_pins=calibration_pins,
        ):
            _ = state  # RunStarted is the genesis event; prior state ignored.
            return Run(
                id=run_id,
                name=RunName(name),
                plan_id=plan_id,
                subject_id=subject_id,
                raid=raid,
                status=RunStatus.RUNNING,
                override_parameters=override_parameters,
                effective_parameters=effective_parameters,
                triggered_by=triggered_by,
                reading_logbook_id=None,
                external_refs=frozenset(
                    ExternalRef(scheme=ref["scheme"], id=ref["id"]) for ref in external_refs
                ),
                campaign_id=campaign_id,
                last_adjusted_at=None,
                adjustment_count=0,
                # Phase 12b: AsShot anchor set at genesis (frozenset for in-
                # memory equality semantics; the event carries a tuple for
                # deterministic wire byte ordering).
                calibration_pins=frozenset(calibration_pins),
            )
        case RunHeld():
            prior = require_state(state, "RunHeld")
            return Run(
                id=prior.id,
                name=prior.name,
                plan_id=prior.plan_id,
                subject_id=prior.subject_id,
                raid=prior.raid,
                status=RunStatus.HELD,
                override_parameters=prior.override_parameters,
                effective_parameters=prior.effective_parameters,
                triggered_by=prior.triggered_by,
                reading_logbook_id=prior.reading_logbook_id,
                external_refs=prior.external_refs,
                campaign_id=prior.campaign_id,
                last_adjusted_at=prior.last_adjusted_at,
                adjustment_count=prior.adjustment_count,
                # Phase 12b AsShot invariant: never change after start.
                calibration_pins=prior.calibration_pins,
            )
        case RunResumed():
            prior = require_state(state, "RunResumed")
            return Run(
                id=prior.id,
                name=prior.name,
                plan_id=prior.plan_id,
                subject_id=prior.subject_id,
                raid=prior.raid,
                status=RunStatus.RUNNING,
                override_parameters=prior.override_parameters,
                effective_parameters=prior.effective_parameters,
                triggered_by=prior.triggered_by,
                reading_logbook_id=prior.reading_logbook_id,
                external_refs=prior.external_refs,
                campaign_id=prior.campaign_id,
                last_adjusted_at=prior.last_adjusted_at,
                adjustment_count=prior.adjustment_count,
                # Phase 12b AsShot invariant: never change after start.
                calibration_pins=prior.calibration_pins,
            )
        case RunCompleted():
            prior = require_state(state, "RunCompleted")
            return Run(
                id=prior.id,
                name=prior.name,
                plan_id=prior.plan_id,
                subject_id=prior.subject_id,
                raid=prior.raid,
                status=RunStatus.COMPLETED,
                override_parameters=prior.override_parameters,
                effective_parameters=prior.effective_parameters,
                triggered_by=prior.triggered_by,
                reading_logbook_id=prior.reading_logbook_id,
                external_refs=prior.external_refs,
                campaign_id=prior.campaign_id,
                last_adjusted_at=prior.last_adjusted_at,
                adjustment_count=prior.adjustment_count,
                # Phase 12b AsShot invariant: never change after start.
                calibration_pins=prior.calibration_pins,
            )
        case RunAborted():
            prior = require_state(state, "RunAborted")
            return Run(
                id=prior.id,
                name=prior.name,
                plan_id=prior.plan_id,
                subject_id=prior.subject_id,
                raid=prior.raid,
                status=RunStatus.ABORTED,
                override_parameters=prior.override_parameters,
                effective_parameters=prior.effective_parameters,
                triggered_by=prior.triggered_by,
                reading_logbook_id=prior.reading_logbook_id,
                external_refs=prior.external_refs,
                campaign_id=prior.campaign_id,
                last_adjusted_at=prior.last_adjusted_at,
                adjustment_count=prior.adjustment_count,
                # Phase 12b AsShot invariant: never change after start.
                calibration_pins=prior.calibration_pins,
            )
        case RunStopped():
            prior = require_state(state, "RunStopped")
            return Run(
                id=prior.id,
                name=prior.name,
                plan_id=prior.plan_id,
                subject_id=prior.subject_id,
                raid=prior.raid,
                status=RunStatus.STOPPED,
                override_parameters=prior.override_parameters,
                effective_parameters=prior.effective_parameters,
                triggered_by=prior.triggered_by,
                reading_logbook_id=prior.reading_logbook_id,
                external_refs=prior.external_refs,
                campaign_id=prior.campaign_id,
                last_adjusted_at=prior.last_adjusted_at,
                adjustment_count=prior.adjustment_count,
                # Phase 12b AsShot invariant: never change after start.
                calibration_pins=prior.calibration_pins,
            )
        case RunTruncated():
            prior = require_state(state, "RunTruncated")
            return Run(
                id=prior.id,
                name=prior.name,
                plan_id=prior.plan_id,
                subject_id=prior.subject_id,
                raid=prior.raid,
                status=RunStatus.TRUNCATED,
                override_parameters=prior.override_parameters,
                effective_parameters=prior.effective_parameters,
                triggered_by=prior.triggered_by,
                reading_logbook_id=prior.reading_logbook_id,
                external_refs=prior.external_refs,
                campaign_id=prior.campaign_id,
                last_adjusted_at=prior.last_adjusted_at,
                adjustment_count=prior.adjustment_count,
                # Phase 12b AsShot invariant: never change after start.
                calibration_pins=prior.calibration_pins,
            )
        case RunAdjusted(
            effective_parameters=effective_parameters,
            occurred_at=adjusted_at,
        ):
            # Phase 6j: mid-flight steering. Status NOT touched
            # (membership-orthogonal pattern, same as the logbook +
            # campaign arms). Replace effective_parameters with the
            # post-merge snapshot from the event payload; stamp
            # last_adjusted_at; increment adjustment_count.
            prior = require_state(state, "RunAdjusted")
            return Run(
                id=prior.id,
                name=prior.name,
                plan_id=prior.plan_id,
                subject_id=prior.subject_id,
                raid=prior.raid,
                status=prior.status,
                override_parameters=prior.override_parameters,
                effective_parameters=effective_parameters,
                triggered_by=prior.triggered_by,
                reading_logbook_id=prior.reading_logbook_id,
                external_refs=prior.external_refs,
                campaign_id=prior.campaign_id,
                last_adjusted_at=adjusted_at,
                adjustment_count=prior.adjustment_count + 1,
                # Phase 12b AsShot invariant: adjust_run never touches the
                # calibration_pins; per the design memo this is the strongest
                # form of the AsShot rule (even mid-flight steering can't
                # change what calibration the Run was acquired against).
                calibration_pins=prior.calibration_pins,
            )
        case RunReadingLogbookOpened(logbook_id=logbook_id):
            # Lazy open-on-first-write (Phase 6f-5b): preserve all
            # prior state, set reading_logbook_id. Status NOT touched
            # — the logbook is orthogonal to lifecycle.
            prior = require_state(state, "RunReadingLogbookOpened")
            return Run(
                id=prior.id,
                name=prior.name,
                plan_id=prior.plan_id,
                subject_id=prior.subject_id,
                raid=prior.raid,
                status=prior.status,
                override_parameters=prior.override_parameters,
                effective_parameters=prior.effective_parameters,
                triggered_by=prior.triggered_by,
                reading_logbook_id=logbook_id,
                external_refs=prior.external_refs,
                campaign_id=prior.campaign_id,
                last_adjusted_at=prior.last_adjusted_at,
                adjustment_count=prior.adjustment_count,
                # Phase 12b AsShot invariant: never change after start.
                calibration_pins=prior.calibration_pins,
            )
        case RunCampaignAssigned(campaign_id=campaign_id):
            # Phase 6i-c: post-hoc membership assignment from
            # `add_run_to_campaign` slice. One-Campaign-per-Run invariant
            # is enforced at the decider (prior campaign_id must be
            # None); the evolver trusts the event log. Status NOT
            # touched -- membership is orthogonal to lifecycle.
            prior = require_state(state, "RunCampaignAssigned")
            return Run(
                id=prior.id,
                name=prior.name,
                plan_id=prior.plan_id,
                subject_id=prior.subject_id,
                raid=prior.raid,
                status=prior.status,
                override_parameters=prior.override_parameters,
                effective_parameters=prior.effective_parameters,
                triggered_by=prior.triggered_by,
                reading_logbook_id=prior.reading_logbook_id,
                external_refs=prior.external_refs,
                campaign_id=campaign_id,
                last_adjusted_at=prior.last_adjusted_at,
                adjustment_count=prior.adjustment_count,
                # Phase 12b AsShot invariant: never change after start.
                calibration_pins=prior.calibration_pins,
            )
        case RunCampaignUnassigned():
            # Phase 6i-c: post-hoc membership removal from
            # `remove_run_from_campaign` slice. Clears campaign_id back
            # to None. The decider enforces that the prior campaign_id
            # matches the event's campaign_id; the evolver trusts the
            # event log. Status NOT touched.
            prior = require_state(state, "RunCampaignUnassigned")
            return Run(
                id=prior.id,
                name=prior.name,
                plan_id=prior.plan_id,
                subject_id=prior.subject_id,
                raid=prior.raid,
                status=prior.status,
                override_parameters=prior.override_parameters,
                effective_parameters=prior.effective_parameters,
                triggered_by=prior.triggered_by,
                reading_logbook_id=prior.reading_logbook_id,
                external_refs=prior.external_refs,
                campaign_id=None,
                last_adjusted_at=prior.last_adjusted_at,
                adjustment_count=prior.adjustment_count,
                # Phase 12b AsShot invariant: never change after start.
                calibration_pins=prior.calibration_pins,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[RunEvent]) -> Run | None:
    """Replay a stream of events from the empty initial state."""
    state: Run | None = None
    for event in events:
        state = evolve(state, event)
    return state
