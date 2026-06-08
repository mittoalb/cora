"""The `ListCredentials` query: keyset-paginated list from
`proj_federation_credential_summary`.

Three optional filters in canonical form:

  - `facility_code` (single-value, exact-match): scope to a single
    facility's credentials.
  - `purpose` (`CredentialPurpose` value-string): scope to one of the
    six purposes (Signing / Verification / Authentication /
    Encryption / SealOnlineSigning / SealOfflineRoot).
  - `status` (`CredentialStatus` value-string): scope to one of the
    three lifecycle values (Active / Rotating / Revoked).

Pagination via `cursor` + `limit` (keyset), matching the cross-BC
`list_query` factory. Cursor encodes `(registered_at, credential_id)`;
`registered_at` is set once at genesis (immutable), so it is a stable
keyset key.

NOTE: opaque secret material (`secret_ref`, `public_material_ref`,
`rotation_pending_*_ref`) is intentionally OMITTED from the list
projection columns surfaced via this slice for vault hygiene; fetch
those via `get_credential` when needed.
"""

from dataclasses import dataclass
from typing import Literal

CredentialPurposeFilter = Literal[
    "Signing",
    "Verification",
    "Authentication",
    "Encryption",
    "SealOnlineSigning",
    "SealOfflineRoot",
]
CredentialStatusFilter = Literal["Active", "Rotating", "Revoked"]


@dataclass(frozen=True)
class ListCredentials:
    """List credentials with cursor pagination + facility / purpose / status filters."""

    cursor: str | None = None
    limit: int = 50
    facility_code: str | None = None
    purpose: CredentialPurposeFilter | None = None
    status: CredentialStatusFilter | None = None
