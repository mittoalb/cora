"""Key-separation invariant guard for the Seal singleton.

Per [[project_federation_port_design]] sec-4 AH#15 strengthening, the
online (warm) signing key and the offline (cold) root key on a
Seal MUST never equal each other. Equality would collapse the
cold-root attestation guarantee: an attacker compromising the warm
key would also gain root authority.

Every transition decider that touches `online_credential_id` or
`offline_credential_id` (`initialize_seal`, `rotate_seal_online_key`,
plus any future offline-root-rotation slice) MUST call
`verify_key_separation(state)` against the *prospective*
post-transition state before commit. The helper raises
`SealKeyCollisionError` on violation; the slice routes that to
HTTP 422.

The helper does NOT perform cross-purpose binding checks (that's the
decider's job: load the referenced Credentials and verify each one's
`CredentialPurpose` matches the slot, raising
`SealKeyPurposeMismatchError` on violation). Separation and
purpose are orthogonal failure modes; keeping them distinct keeps the
error classes load-bearing for HTTP routing.
"""

from cora.federation.aggregates.seal.state import (
    Seal,
    SealKeyCollisionError,
)


def verify_key_separation(state: Seal) -> None:
    """Raise `SealKeyCollisionError` when online and offline refs are equal.

    Call against the *prospective* post-transition state from every
    decider that mutates either key ref. Returns None on the happy
    path (refs differ).
    """
    if state.online_credential_id == state.offline_credential_id:
        raise SealKeyCollisionError(
            facility_id=state.facility_code.value,
            shared_credential_id=state.online_credential_id,
        )


__all__ = ["verify_key_separation"]
