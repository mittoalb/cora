"""The `RegisterCredential` command: intent dataclass for this slice.

Carries the caller-controlled fields for registering a new Credential:

  - `facility_id`: opaque string id of the facility this credential
    binds to. String-typed because facility identity is external to
    CORA; we do NOT mint facility ids here.
  - `audience`: opaque string scoping the credential to a particular
    peer / endpoint. Required, non-empty after trim.
  - `purpose`: closed enum (`CredentialPurpose`) selecting which of the
    six roles this credential plays (Signing / Verification /
    Authentication / Encryption / SealOnlineSigning / SealOfflineRoot).
  - `secret_ref`: opaque pointer (URI, KMS ARN, vault path) to the
    secret material held in a `SecretStore` adapter. Per AH#6 of the
    locked design the aggregate NEVER carries raw secret bytes; the
    caller is responsible for landing the bytes in SecretStore before
    invoking this slice.
  - `public_material_ref`: opaque pointer to the public counterpart
    when the purpose has one (verification key, encryption-public-key,
    certificate handle). `None` for purposes that are symmetric or
    where the public half lives elsewhere.
  - `expires_at`: OPTIONAL contractual upper bound. Seal online-signing
    credentials may declare a hard expiry; offline-root credentials may
    not. When set, must lie strictly after the server's now.

Server-side concerns (new credential id, wall-clock timestamp,
correlation id, per-event ids, `registered_by_actor_id`) are injected
by the handler from infrastructure ports / the request envelope.
"""

from dataclasses import dataclass
from datetime import datetime

from cora.federation.aggregates.credential import CredentialPurpose


@dataclass(frozen=True, slots=True)
class RegisterCredential:
    """Register a new Credential (genesis; lands in Active)."""

    facility_id: str
    audience: str
    purpose: CredentialPurpose
    secret_ref: str
    public_material_ref: str | None
    expires_at: datetime | None
