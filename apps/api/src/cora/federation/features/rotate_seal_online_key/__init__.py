"""Vertical slice for the `RotateSealOnlineKey` command.

Module-as-namespace surface, symmetric with the other Federation
Seal lifecycle slices:

    from cora.federation.features import rotate_seal_online_key

    cmd = rotate_seal_online_key.RotateSealOnlineKey(
        facility_id="aps", new_online_key_ref=...
    )
    handler = rotate_seal_online_key.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)

Mid-lifecycle Live -> Live transition that swaps the online (warm)
signing key. Strict-not-idempotent: rotating to the same ref the slot
already holds raises `SealCannotRotateError` (HTTP 409); rotating
against a Republishing Seal raises `SealCannotRotateError`; rotating
to a ref equal to `offline_key_ref` raises `SealKeyCollisionError`
(HTTP 422) via the `_key_separation` helper.

Cross-BC: this slice writes `SealOnlineKeyRotated` on the Federation
Seal stream AND a `DecisionRegistered` audit on the Decision stream
in one transaction. Rotating an online key is a security-touching
action (offline-root-authorised warm-key swap), so the audit emission
is atomic with the rotation; mirrors the `revoke_credential` cross-BC
mid-lifecycle pattern.
"""

from cora.federation.features.rotate_seal_online_key import tool
from cora.federation.features.rotate_seal_online_key.command import (
    RotateSealOnlineKey,
)
from cora.federation.features.rotate_seal_online_key.decider import decide
from cora.federation.features.rotate_seal_online_key.handler import Handler, bind
from cora.federation.features.rotate_seal_online_key.route import router

__all__ = [
    "Handler",
    "RotateSealOnlineKey",
    "bind",
    "decide",
    "router",
    "tool",
]
