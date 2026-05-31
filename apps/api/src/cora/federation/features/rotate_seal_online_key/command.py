"""The `RotateSealOnlineKey` command: intent dataclass for this slice.

`facility_id` selects the Seal singleton; `new_online_credential_id` is the
fresh Credential.id to install in the online (warm) slot. The principal
id of the invoker is supplied separately by the application handler at
call time and stamped onto `SealOnlineKeyRotated` as
`rotated_by_actor_id`.

Rotation is a security-touching action (the offline root authorises a
warm-key swap, typically in response to suspected compromise or planned
rollover): the slice writes the domain event AND a paired
`DecisionRegistered` audit on the Decision BC stream in one transaction,
matching the `register_credential` / `revoke_credential` cross-BC
pattern.

Strict-not-idempotent at the decider: rotating against a Republishing
Seal raises `SealCannotRotateError` (HTTP 409); rotating to the same
ref the slot already holds raises `SealCannotRotateError` (no-op
rotations are rejected so the audit gesture is always meaningful);
rotating to a ref equal to `offline_credential_id` raises
`SealKeyCollisionError` (HTTP 422) via the `_key_separation` helper.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RotateSealOnlineKey:
    """Operator rotates the Seal singleton's online (warm) signing key.

    Source state Live (Republishing is rejected). The new ref must
    differ from both the current online ref (no-op rotation rejected)
    and the current offline ref (key-separation invariant). The
    referenced Credential's purpose binding is checked at a future
    stage; today the slice accepts the ref opaquely per the eventual-
    consistency carve-out documented in
    [[project_federation_port_design]].

    `signed_by_offline_root` is the operator's affirmation that the
    offline (cold) root authorised this rotation. Required (no default)
    because the audit gesture is security-meaningful: the SOC must be
    able to scrub the Decision-BC stream and distinguish ceremonies
    where the offline root countersigned from those where it did not.
    """

    facility_id: str
    new_online_credential_id: UUID
    signed_by_offline_root: bool
