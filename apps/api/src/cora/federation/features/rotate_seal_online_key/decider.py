"""Pure decider for the `RotateSealOnlineKey` command.

Live -> Live transition that swaps `online_key_ref` to a fresh
Credential. Strict-not-idempotent: re-rotating to the same ref the
slot already holds raises `SealCannotRotateError` so the audit
gesture stays meaningful (the offline-root authorises a real change
each time).

`rotated_by_actor_id` is handler-injected from the request envelope's
`principal_id` (capture-don't-recompute) and stamped onto the emitted
`SealOnlineKeyRotated` event for the audit denorm.

The key-separation invariant (sec-4 AH#15) is enforced by building the
prospective post-transition `Seal` state with the new online ref and
calling `verify_key_separation` before returning events. The helper
raises `SealKeyCollisionError` when `new_online_key_ref` would equal
`offline_key_ref`; HTTP routes this to 422.

The cross-aggregate purpose-binding check (verify the new credential's
purpose is `SealOnlineSigning`) is deferred pending a
`CredentialLookup` port; today the slice accepts the ref opaquely per
the eventual-consistency carve-out documented in
[[project_federation_port_design]]. `SealKeyPurposeMismatchError`
stays defined in `state.py` for a future iter to wire.

## Validation

  - State must not be None (Seal must exist) -> SealNotFoundError
  - Current status must be Live -> SealCannotRotateError
  - new_online_key_ref must differ from current online_key_ref
    -> SealCannotRotateError (no-op rotation rejected)
  - new_online_key_ref must differ from offline_key_ref
    -> SealKeyCollisionError (via verify_key_separation helper)
"""

from dataclasses import replace
from datetime import datetime
from uuid import UUID

from cora.federation.aggregates.seal import (
    Seal,
    SealCannotRotateError,
    SealNotFoundError,
    SealOnlineKeyRotated,
    SealStatus,
    verify_key_separation,
)
from cora.federation.features.rotate_seal_online_key.command import (
    RotateSealOnlineKey,
)


def decide(
    state: Seal | None,
    command: RotateSealOnlineKey,
    *,
    now: datetime,
    rotated_by_actor_id: UUID,
) -> list[SealOnlineKeyRotated]:
    """Decide the events produced by rotating the Seal online key.

    Invariants:
      - State must not be None -> SealNotFoundError
      - state.status must be Live -> SealCannotRotateError
      - new_online_key_ref must differ from state.online_key_ref
        -> SealCannotRotateError (no-op rotation rejected)
      - new_online_key_ref must differ from state.offline_key_ref
        -> SealKeyCollisionError (via verify_key_separation)
    """
    if state is None:
        raise SealNotFoundError(command.facility_id)
    if state.status is not SealStatus.LIVE:
        raise SealCannotRotateError(state.facility_id, state.status)
    if command.new_online_key_ref == state.online_key_ref:
        raise SealCannotRotateError(state.facility_id, state.status)

    prospective = replace(state, online_key_ref=command.new_online_key_ref)
    verify_key_separation(prospective)

    return [
        SealOnlineKeyRotated(
            facility_id=state.facility_id,
            new_online_key_ref=command.new_online_key_ref,
            signed_by_offline_root=command.signed_by_offline_root,
            rotated_by_actor_id=rotated_by_actor_id,
            occurred_at=now,
        )
    ]


__all__ = ["decide"]
