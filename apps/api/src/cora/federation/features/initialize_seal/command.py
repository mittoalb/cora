"""The `InitializeSeal` command: intent dataclass for this slice.

Carries the caller-controlled fields for minting the Seal singleton
for a facility:

  - `facility_id`: opaque string id of the facility this Seal binds
    to. String-typed because facility identity is external to CORA;
    we do NOT mint facility ids. Required, non-empty after trim.
    Doubles as the singleton identity (one Seal per facility); the
    handler derives the stream UUID deterministically via
    `seal_stream_id(facility_id)`.
  - `online_key_ref`: Credential.id of the warm signing key
    (purpose `SealOnlineSigning`). MUST differ from
    `offline_key_ref` (key-separation invariant enforced by the
    decider via the `_key_separation` helper).
  - `offline_key_ref`: Credential.id of the cold root key
    (purpose `SealOfflineRoot`). MUST differ from
    `online_key_ref`.

Server-side concerns (wall-clock timestamp, correlation id, per-event
ids, `initialized_by_actor_id`) are injected by the handler from
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

    facility_id: str
    online_key_ref: UUID
    offline_key_ref: UUID
