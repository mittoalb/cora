"""Adapters Federation BC ships for cross-BC ports.

- `PostgresCredentialLookup` implementing
  `cora.infrastructure.ports.CredentialLookup` (consumed by Federation
  BC's `initialize_seal` and `rotate_seal_online_key` handlers).
- `PostgresFacilityLookup` implementing
  `cora.infrastructure.ports.FacilityLookup` (consumed by Federation
  BC's `register_facility` handler for parent.kind=Site validation,
  and by Sub-Slice B's `add_facility_trust_anchor_credential` decider).
"""

from cora.federation.adapters.postgres_credential_lookup import PostgresCredentialLookup
from cora.federation.adapters.postgres_facility_lookup import PostgresFacilityLookup

__all__ = ["PostgresCredentialLookup", "PostgresFacilityLookup"]
