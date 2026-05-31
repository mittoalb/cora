"""Adapters Federation BC ships for cross-BC ports.

Today: `PostgresCredentialLookup` implementing
`cora.infrastructure.ports.CredentialLookup` (consumed by Federation
BC's `initialize_seal` and `rotate_seal_online_key` handlers).
"""

from cora.federation.adapters.postgres_credential_lookup import PostgresCredentialLookup

__all__ = ["PostgresCredentialLookup"]
