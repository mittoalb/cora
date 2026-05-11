"""Pure decider for the `VersionCapability` command.

Multi-source-state transition: `Defined | Versioned -> Versioned`.
Both Defined (first revision) and Versioned (subsequent revisions)
are valid sources; only Deprecated is rejected.

Source-state guard uses tuple-membership (same precedent as
decommission_asset). The decider validates `version_tag` defensively
via `InvalidCapabilityVersionTagError` so direct in-process callers
get the same protection as API-boundary callers.

## Deliberate divergence from strict-not-idempotent

Most update-style transitions in the codebase are strict-not-
idempotent: re-mounting / re-activating / re-decommissioning raises.
Version_capability is the EXCEPTION — calling
`version_capability("v2")` twice in a row both succeed, producing
two `CapabilityVersioned` events with the same tag. This is
intentional: re-attestation is a legitimate audit moment ("the
operator confirmed v2 again on date X"), and the multi-source
Versioned → Versioned transition already permits the operation
structurally. Tightening to "must use a different tag" would couple
the decider to history-walking, which the eventual-consistency
stance avoids. Pinned by `test_decide_allows_versioning_with_same_tag_for_re_attestation`.

Invariants:
  - State must not be None -> CapabilityNotFoundError
  - command.version_tag must be 1-50 chars after trimming
    -> InvalidCapabilityVersionTagError
  - State.status must be in {Defined, Versioned}
    -> CapabilityCannotVersionError(current_status=...)
"""

from datetime import datetime

from cora.equipment.aggregates.capability import (
    CAPABILITY_VERSION_TAG_MAX_LENGTH,
    Capability,
    CapabilityCannotVersionError,
    CapabilityNotFoundError,
    CapabilityStatus,
    CapabilityVersioned,
    InvalidCapabilityVersionTagError,
)
from cora.equipment.features.version_capability.command import VersionCapability

_VERSIONABLE_STATUSES: tuple[CapabilityStatus, ...] = (
    CapabilityStatus.DEFINED,
    CapabilityStatus.VERSIONED,
)


def decide(
    state: Capability | None,
    command: VersionCapability,
    *,
    now: datetime,
) -> list[CapabilityVersioned]:
    """Decide the events produced by versioning an existing capability."""
    if state is None:
        raise CapabilityNotFoundError(command.capability_id)
    trimmed = command.version_tag.strip()
    if not trimmed or len(trimmed) > CAPABILITY_VERSION_TAG_MAX_LENGTH:
        raise InvalidCapabilityVersionTagError(command.version_tag)
    if state.status not in _VERSIONABLE_STATUSES:
        raise CapabilityCannotVersionError(state.id, current_status=state.status)
    return [
        CapabilityVersioned(
            capability_id=state.id,
            version_tag=trimmed,
            occurred_at=now,
        )
    ]
