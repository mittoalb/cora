"""Pure decider for the `VersionPlan` command.

Multi-source-state transition: `Defined | Versioned -> Versioned`.
Both Defined (first revision) and Versioned (subsequent revisions)
are valid sources; only Deprecated is rejected.

## Deliberate divergence from strict-not-idempotent

Same as version_practice (Recipe 6d-2), version_method (Recipe 6b),
and version_family (Equipment 5f-2): re-versioning with the same
tag succeeds and emits a fresh event. Re-attestation is a legitimate
audit moment. Pinned by
`test_decide_allows_versioning_with_same_tag_for_re_attestation`.

## Content hash

Computed here per non-determinism principle: the decider captures
the SHA-256 of the canonical body bytes for the Plan's content
subset and pins it in the emitted PlanVersioned event. Re-attesting
the same content yields the same hash (intended equivalence-detection
semantic, Bazel input/output split pattern). The content subset is
fixed at `name + method_id + practice_id + asset_ids +
default_parameters + wires` per [[project_content_addressed_identity_design]];
status, version (the index), and identity fields are excluded.

Invariants:
  - State must not be None -> PlanNotFoundError
  - command.version_tag must be 1-50 chars after trimming
    -> InvalidPlanVersionTagError
  - State.status must be in {Defined, Versioned}
    -> PlanCannotVersionError(current_status=...)

Note: this decider does NOT re-validate the bind-time invariants
(family superset, upstream-not-deprecated, no-decommissioned-
asset). Versioning a Plan is a label change on an existing binding,
not a re-bind. Re-validation against current upstream state is the
job of a future ongoing-satisfiability projection (gate-review Q3
deferred option iii').
"""

from datetime import datetime

from cora.infrastructure.content_hash import compute_content_hash
from cora.infrastructure.signing import event_type_to_payload_type
from cora.recipe.aggregates.plan import (
    PLAN_VERSION_TAG_MAX_LENGTH,
    InvalidPlanVersionTagError,
    Plan,
    PlanCannotVersionError,
    PlanNotFoundError,
    PlanStatus,
    PlanVersioned,
)
from cora.recipe.features.version_plan.command import VersionPlan

_VERSIONABLE_STATUSES: tuple[PlanStatus, ...] = (
    PlanStatus.DEFINED,
    PlanStatus.VERSIONED,
)

_PLAN_VERSIONED_PAYLOAD_TYPE = event_type_to_payload_type("PlanVersioned")


def _content_subset(state: Plan) -> dict[str, object]:
    """Build the content subset hashed into PlanVersioned.content_hash.

    Mirrors [[project_content_addressed_identity_design]] §"Plan.content_hash":
    `name + method_id + practice_id + asset_ids + default_parameters
    + wires`. UUIDs render as strings (json-serializable), frozensets
    render as sorted lists (deterministic across processes;
    `canonical_body_bytes` would sort either way but the explicit
    materialization keeps this subset readable as a "what's hashed"
    spec, not a black-box dump). `wires` renders as a sorted list of
    4-tuples-of-strings; the outer sort is lexicographic over the
    string tuple form, anti-hook #12 (frozensets must be coerced to
    sorted lists deterministically before hashing). method_id is
    Optional on Plan state (additive-evolution default for legacy
    Plans) but always concrete for any Plan that has reached
    Versioned status — well-formed streams pass through PlanDefined
    which carries method_id. The mapping is locked here at the
    decider rather than computed off state by reflection, so any
    future field added to Plan state requires an explicit decision
    about whether it participates in content identity (anti-hook
    #10 from the design lock).
    """
    return {
        "name": state.name.value,
        "method_id": str(state.method_id) if state.method_id is not None else None,
        "practice_id": str(state.practice_id),
        "asset_ids": sorted(str(a) for a in state.asset_ids),
        "default_parameters": state.default_parameters,
        "wires": sorted(
            (
                str(w.source_asset_id),
                w.source_port_name,
                str(w.target_asset_id),
                w.target_port_name,
            )
            for w in state.wires
        ),
    }


def decide(
    state: Plan | None,
    command: VersionPlan,
    *,
    now: datetime,
) -> list[PlanVersioned]:
    """Decide the events produced by versioning an existing plan."""
    if state is None:
        raise PlanNotFoundError(command.plan_id)
    trimmed = command.version_tag.strip()
    if not trimmed or len(trimmed) > PLAN_VERSION_TAG_MAX_LENGTH:
        raise InvalidPlanVersionTagError(command.version_tag)
    if state.status not in _VERSIONABLE_STATUSES:
        raise PlanCannotVersionError(state.id, current_status=state.status)
    content_hash = compute_content_hash(_PLAN_VERSIONED_PAYLOAD_TYPE, _content_subset(state))
    return [
        PlanVersioned(
            plan_id=state.id,
            version_tag=trimmed,
            occurred_at=now,
            content_hash=content_hash,
        )
    ]
