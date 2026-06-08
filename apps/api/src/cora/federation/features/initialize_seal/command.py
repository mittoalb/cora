"""The `InitializeSeal` command: intent dataclass for this slice.

Carries the caller-controlled fields for minting the Seal singleton
for a facility:

  - `facility_code`: cross-deployment convergent facility slug. Bare
    `str` on the command DTO; the handler wraps it as a `FacilityCode`
    VO at the port edge before threading it into the decider, the
    facility lookup, and the `seal_stream_id` derivation. Required,
    non-empty after trim. Doubles as the singleton identity (one
    Seal per facility).
  - `online_credential_id`: Credential.id of the warm signing key
    (purpose `SealOnlineSigning`). MUST differ from
    `offline_credential_id` (key-separation invariant enforced by the
    decider via the `_key_separation` helper).
  - `offline_credential_id`: Credential.id of the cold root key
    (purpose `SealOfflineRoot`). MUST differ from
    `online_credential_id`.

Server-side concerns (wall-clock timestamp, correlation id, per-event
ids, `initialized_by`) are injected by the handler from
infrastructure ports / the request envelope per the
capture-don't-recompute principle. Per-slice cross-aggregate purpose
binding (verifying each Credential's purpose matches the slot) is
deferred to a future iter pending a CredentialLookup port; the
key-separation invariant ships today.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class InitializeSeal:
    """Initialize the Seal singleton for a facility (genesis; lands in Live)."""

    facility_code: str
    online_credential_id: UUID
    offline_credential_id: UUID
