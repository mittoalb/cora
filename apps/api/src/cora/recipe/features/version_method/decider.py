"""Pure decider for the `VersionMethod` command.

Multi-source-state transition: `Defined | Versioned -> Versioned`.
Both Defined (first revision) and Versioned (subsequent revisions)
are valid sources; only Deprecated is rejected.

Source-state guard uses tuple-membership (same precedent as
decommission_asset / version_family). The decider validates
`version_tag` defensively via `InvalidMethodVersionTagError` so
direct in-process callers get the same protection as API-boundary
callers.

## Deliberate divergence from strict-not-idempotent

Same as `version_family` (Equipment 5f-2): re-versioning with
the same tag succeeds and emits a fresh event. Re-attestation is a
legitimate audit moment ("the operator confirmed v2 again on date
X"). Tightening would couple the decider to history-walking, which
the eventual-consistency stance avoids. Pinned by
`test_decide_allows_versioning_with_same_tag_for_re_attestation`.

## Content hash

Computed here per non-determinism principle: the decider captures
the SHA-256 of the canonical body bytes for the Method's content
subset and pins it in the emitted MethodVersioned event. Re-attesting
the same content yields the same hash (intended equivalence-detection
semantic, Bazel input/output split pattern). The content subset is
fixed at `name + parameters_schema + capability_id + needed_families
+ needed_supplies` per [[project_content_addressed_identity_design]];
status, version (the index), and identity fields are excluded.

Invariants:
  - State must not be None -> MethodNotFoundError
  - command.version_tag must be 1-50 chars after trimming
    -> InvalidMethodVersionTagError
  - State.status must be in {Defined, Versioned}
    -> MethodCannotVersionError(current_status=...)
"""

from datetime import datetime

from cora.infrastructure.content_hash import compute_content_hash
from cora.infrastructure.signing import event_type_to_payload_type
from cora.recipe.aggregates.method import (
    METHOD_VERSION_TAG_MAX_LENGTH,
    InvalidMethodVersionTagError,
    Method,
    MethodCannotVersionError,
    MethodNotFoundError,
    MethodStatus,
    MethodVersioned,
)
from cora.recipe.features.version_method.command import VersionMethod

_VERSIONABLE_STATUSES: tuple[MethodStatus, ...] = (
    MethodStatus.DEFINED,
    MethodStatus.VERSIONED,
)

_METHOD_VERSIONED_PAYLOAD_TYPE = event_type_to_payload_type("MethodVersioned")


def _content_subset(state: Method) -> dict[str, object]:
    """Build the content subset hashed into MethodVersioned.content_hash.

    Mirrors [[project_content_addressed_identity_design]] §"Method.content_hash":
    `name + parameters_schema + capability_id + needed_families +
    needed_supplies`. UUIDs render as strings (json-serializable),
    frozensets render as sorted lists (deterministic across processes;
    `canonical_body_bytes` would sort either way but the explicit
    materialization keeps this subset readable as a "what's hashed"
    spec, not a black-box dump). The mapping is locked here at the
    decider rather than computed off state by reflection, so any
    future field added to Method state requires an explicit decision
    about whether it participates in content identity (anti-hook #10
    from the design lock).
    """
    return {
        "name": state.name.value,
        "parameters_schema": state.parameters_schema,
        "capability_id": str(state.capability_id) if state.capability_id is not None else None,
        "needed_families": sorted(str(f) for f in state.needed_families),
        "needed_supplies": sorted(state.needed_supplies),
    }


def decide(
    state: Method | None,
    command: VersionMethod,
    *,
    now: datetime,
) -> list[MethodVersioned]:
    """Decide the events produced by versioning an existing method."""
    if state is None:
        raise MethodNotFoundError(command.method_id)
    trimmed = command.version_tag.strip()
    if not trimmed or len(trimmed) > METHOD_VERSION_TAG_MAX_LENGTH:
        raise InvalidMethodVersionTagError(command.version_tag)
    if state.status not in _VERSIONABLE_STATUSES:
        raise MethodCannotVersionError(state.id, current_status=state.status)
    content_hash = compute_content_hash(_METHOD_VERSIONED_PAYLOAD_TYPE, _content_subset(state))
    return [
        MethodVersioned(
            method_id=state.id,
            version_tag=trimmed,
            occurred_at=now,
            content_hash=content_hash,
        )
    ]
