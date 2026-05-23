"""Actor PII vault: profile dataclass + ProfileStore port + adapters.

Per [[project_pii_vault]] strategic lock and
[[project_pii_vault_implementation_design]] Stage-1: human-facing
Actor PII lives in a mutable side table (`actor_profile`), separate
from the immutable event log. Events never carry PII; this module
owns the read/write path for the mutable rows.

## Module placement

Mirrors `cora/decision/aggregates/decision/entries.py`: the dataclass,
the Protocol, both adapters, and the display-fallback constant all
live in ONE file inside the aggregate folder. Rationale:

  - The shape (Profile fields) is Access-BC domain vocabulary, not
    infrastructure.
  - The Postgres adapter's SQL is column-shape-aware; splitting infra
    from domain modules would require either a generic SQL builder
    or duplicate column lists.
  - Same trade-off `events.py` per-aggregate modules made.

## Erasure model

The `forget_actor` slice does scrub-then-DELETE on the profile row
in the same transaction as the `ActorProfileForgotten` event append.
The scrub UPDATE writes empty values before DELETE so the dead tuple
bytes (linger until VACUUM rewrites the page) no longer contain PII.
See [[project_pii_vault_implementation_design]] for the full handler
shape.

## Display fallback

Post-erasure, the `actor_id` reference in events remains valid
(pseudonymised per EDPB 01/2025 Example 10). Read paths resolve the
display name via `load_actor_display_name`, which returns the
`DELETED_ACTOR_DISPLAY_NAME` literal when the profile row is absent.
The locale-neutral English literal is locked per the existing
[[project_deferred]] i18n entry (trigger: first non-English facility
deployment).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# (asyncpg's typed-Pool/Connection narrows poorly in strict mode; matches the
# convention in cora/infrastructure/postgres/idempotency.py for the same reason.)

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

import asyncpg

DELETED_ACTOR_DISPLAY_NAME = "<deleted user>"


@dataclass(frozen=True)
class Profile:
    """One mutable row in the actor_profile PII vault.

    Today carries `name` only; future PII fields (email, phone, ORCID,
    affiliation) land as nullable columns via additive ALTER TABLE
    per [[project_deferred]] PII vault entry.
    """

    actor_id: UUID
    name: str
    created_at: datetime
    updated_at: datetime


class ProfileStore(Protocol):
    """Read / write / erase access to the actor_profile table.

    Two implementations: `PostgresProfileStore` (production) and
    `InMemoryProfileStore` (tests / `app_env=test`). Both honor
    at-least-once: callers may retry the same upsert, the store
    dedups via the actor_id PK constraint (Postgres) or the
    in-memory dict (InMemory).
    """

    async def upsert(
        self,
        *,
        actor_id: UUID,
        name: str,
        created_at: datetime,
    ) -> None:
        """Insert a new profile row or update the name on an existing row.

        Used by `register_actor` and `define_agent` slice handlers.
        Idempotent on actor_id PK: retrying the same upsert after a
        partial failure replays cleanly.
        """
        ...

    async def get(self, actor_id: UUID) -> Profile | None:
        """Fetch a profile row by actor_id; returns None if absent (erased or never-registered)."""
        ...

    async def get_many(self, actor_ids: Sequence[UUID]) -> dict[UUID, Profile]:
        """Bulk fetch profiles by actor_id; missing actor_ids are absent from the result."""
        ...

    async def scrub_and_delete(self, conn: asyncpg.Connection, actor_id: UUID) -> None:
        """Scrub PII columns then DELETE the row, IN the caller's transaction.

        Used by `forget_actor` so the erasure is atomic with the
        ActorProfileForgotten event append. The `conn` parameter is
        the asyncpg Connection inside the open transaction.

        Scrub-then-DELETE shape (UPDATE name='' before DELETE) ensures
        the dead tuple bytes (linger until VACUUM) no longer contain
        PII. Postgres-canonical WAL/dead-tuple PII cleanup pattern.

        Idempotent on missing row (rowcount = 0 from both statements).
        """
        ...


_UPSERT_SQL = """
INSERT INTO actor_profile (actor_id, name, created_at, updated_at)
VALUES ($1, $2, $3, $3)
ON CONFLICT (actor_id) DO UPDATE
    SET name = EXCLUDED.name,
        updated_at = now()
"""

_GET_SQL = """
SELECT actor_id, name, created_at, updated_at
FROM actor_profile
WHERE actor_id = $1
"""

_GET_MANY_SQL = """
SELECT actor_id, name, created_at, updated_at
FROM actor_profile
WHERE actor_id = ANY($1::uuid[])
"""

_SCRUB_SQL = "UPDATE actor_profile SET name = '' WHERE actor_id = $1"

_DELETE_SQL = "DELETE FROM actor_profile WHERE actor_id = $1"


def _row_to_profile(row: Any) -> Profile:
    # `row: Any` matches the CORA convention (see list_actors handler);
    # asyncpg's Record stub doesn't narrow column types, so we coerce here.
    return Profile(
        actor_id=row["actor_id"],
        name=str(row["name"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class PostgresProfileStore:
    """asyncpg-backed `ProfileStore` implementation.

    All four methods are idempotent on retry:
      - upsert: ON CONFLICT DO UPDATE (rename-on-retry semantics).
      - get / get_many: pure reads.
      - scrub_and_delete: rowcount = 0 on missing row (no error).
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def upsert(
        self,
        *,
        actor_id: UUID,
        name: str,
        created_at: datetime,
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(_UPSERT_SQL, actor_id, name, created_at)

    async def get(self, actor_id: UUID) -> Profile | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(_GET_SQL, actor_id)
        if row is None:
            return None
        return _row_to_profile(row)

    async def get_many(self, actor_ids: Sequence[UUID]) -> dict[UUID, Profile]:
        if not actor_ids:
            return {}
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(_GET_MANY_SQL, list(actor_ids))
        return {row["actor_id"]: _row_to_profile(row) for row in rows}

    async def scrub_and_delete(self, conn: asyncpg.Connection, actor_id: UUID) -> None:
        # Scrub first (UPDATE name = '') so the dead tuple bytes that
        # linger until VACUUM no longer contain PII. Then DELETE marks
        # the scrubbed version dead. Both statements idempotent on
        # missing row (rowcount = 0).
        await conn.execute(_SCRUB_SQL, actor_id)
        await conn.execute(_DELETE_SQL, actor_id)


class InMemoryProfileStore:
    """In-memory `ProfileStore` for tests and `app_env=test`.

    Mirrors Postgres semantics: on insert, `updated_at = created_at`;
    on update, `updated_at = now(tz=UTC)`. The `conn` parameter on
    `scrub_and_delete` is ignored (no transaction in-memory); the
    contract is preserved at the type level.
    """

    def __init__(self) -> None:
        self._rows: dict[UUID, Profile] = {}

    async def upsert(
        self,
        *,
        actor_id: UUID,
        name: str,
        created_at: datetime,
    ) -> None:
        existing = self._rows.get(actor_id)
        if existing is None:
            self._rows[actor_id] = Profile(
                actor_id=actor_id,
                name=name,
                created_at=created_at,
                updated_at=created_at,
            )
        else:
            self._rows[actor_id] = Profile(
                actor_id=actor_id,
                name=name,
                created_at=existing.created_at,
                updated_at=datetime.now(tz=UTC),
            )

    async def get(self, actor_id: UUID) -> Profile | None:
        return self._rows.get(actor_id)

    async def get_many(self, actor_ids: Sequence[UUID]) -> dict[UUID, Profile]:
        return {aid: self._rows[aid] for aid in actor_ids if aid in self._rows}

    async def scrub_and_delete(self, conn: asyncpg.Connection, actor_id: UUID) -> None:
        _ = conn  # in-memory: no transaction; contract preserved at type level
        self._rows.pop(actor_id, None)


async def load_actor_display_name(profile_store: ProfileStore, actor_id: UUID) -> str:
    """Resolve the display name for an actor_id; tombstone fallback when absent.

    Read-path convention: any handler returning an Actor-display surface
    (REST DTO, MCP response, error message) calls this helper to get a
    UI-safe string. Returns `DELETED_ACTOR_DISPLAY_NAME` when the profile
    row is absent (erased OR never-registered).
    """
    profile = await profile_store.get(actor_id)
    return profile.name if profile else DELETED_ACTOR_DISPLAY_NAME


__all__ = [
    "DELETED_ACTOR_DISPLAY_NAME",
    "InMemoryProfileStore",
    "PostgresProfileStore",
    "Profile",
    "ProfileStore",
    "load_actor_display_name",
]
