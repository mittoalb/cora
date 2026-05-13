"""Bookmark read/write SQL helpers.

The worker's advance loop calls these inside its transaction:

  1. `read_bookmark(conn, name)` -> `(last_transaction_id, last_position)`
     locks the bookmark row FOR UPDATE so concurrent workers (when
     deferred multi-worker arrives) won't double-advance.
  2. `write_bookmark(conn, name, ...)` updates the bookmark and
     resets the failure-tracking columns; commits with the same
     transaction as the projection writes for atomic at-least-once
     delivery.
  3. `write_bookmark_failure(pool, name, error_message)` updates ONLY
     the failure columns in a SEPARATE small transaction (NOT the
     advance-loop transaction, which is rolling back). The bookmark
     position itself stays put so retry semantics are preserved.

Phase 8e-9 added four observability columns to `projection_bookmarks`
(`last_event_recorded_at`, `last_error_at`, `last_error_message`,
`consecutive_failures`). Success path resets failure columns to NULL
+ counter to 0 atomically with the position advance; failure path
increments the counter and records the error message in its own
small transaction. Pre-positions for the full read-side observability
surface (admin endpoint + lag sampler + OTel) which stays deferred
until the trigger fires.

Bookmark rows are created by per-projection migrations (`INSERT INTO
projection_bookmarks (name) VALUES (...) ON CONFLICT DO NOTHING`),
not by the worker — registering a projection without its migration
having landed will fail loudly at first advance, which is the
behavior we want.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import datetime

import asyncpg

from cora.infrastructure.projection.handler import ConnectionLike

# Bound the bookmark UPDATE size. Operators see error class + first
# part of message; full traceback goes to OTel spans when the full
# observability surface ships.
_ERROR_MESSAGE_MAX_CHARS = 500

_READ_BOOKMARK_SQL = """
SELECT last_transaction_id::text AS last_tx, last_position
FROM projection_bookmarks
WHERE name = $1
FOR UPDATE
"""
# `last_transaction_id::text` for the same reason as `events`: asyncpg
# 0.31 has no built-in xid8 OUTPUT codec, so we cast and parse to int.

_WRITE_BOOKMARK_SQL = """
UPDATE projection_bookmarks
SET last_transaction_id    = $2::xid8,
    last_position          = $3,
    last_event_recorded_at = $4,
    last_error_at          = NULL,
    last_error_message     = NULL,
    consecutive_failures   = 0,
    updated_at             = now()
WHERE name = $1
"""

_WRITE_BOOKMARK_FAILURE_SQL = """
UPDATE projection_bookmarks
SET last_error_at        = now(),
    last_error_message   = $2,
    consecutive_failures = consecutive_failures + 1,
    updated_at           = now()
WHERE name = $1
"""


class MissingBookmarkError(Exception):
    """No bookmark row exists for the given projection name. Indicates
    the projection's migration didn't land (or its `INSERT INTO
    projection_bookmarks` statement was missed)."""

    def __init__(self, name: str) -> None:
        super().__init__(
            f"No projection_bookmarks row for {name!r}. The projection's "
            "migration must include an `INSERT INTO projection_bookmarks "
            "(name) VALUES (...) ON CONFLICT DO NOTHING` statement."
        )
        self.name = name


async def read_bookmark(
    conn: ConnectionLike,
    name: str,
) -> tuple[int, int]:
    """Read `(last_transaction_id, last_position)` for the projection.

    Locks the row FOR UPDATE; caller is responsible for the surrounding
    transaction. Raises `MissingBookmarkError` if the row doesn't exist.
    """
    row = await conn.fetchrow(_READ_BOOKMARK_SQL, name)
    if row is None:
        raise MissingBookmarkError(name)
    return int(row["last_tx"]), int(row["last_position"])


async def write_bookmark(
    conn: ConnectionLike,
    name: str,
    *,
    last_transaction_id: int,
    last_position: int,
    last_event_recorded_at: datetime,
) -> None:
    """Update the bookmark to the new (last_tx, last_pos) cursor and
    reset failure-tracking columns.

    Called inside the advance-loop transaction; the position advance
    + failure-reset commit together with the projection writes for
    atomic at-least-once delivery + observability consistency.
    """
    await conn.execute(
        _WRITE_BOOKMARK_SQL,
        name,
        last_transaction_id,
        last_position,
        last_event_recorded_at,
    )


async def write_bookmark_failure(
    pool: asyncpg.Pool,
    name: str,
    *,
    error_message: str,
) -> None:
    """Record an advance-loop failure in a SEPARATE small transaction.

    Phase 8e-9 observability hook. Called from the advance-loop
    exception handler AFTER the failed batch has rolled back.
    Increments `consecutive_failures` and records `last_error_at` +
    `last_error_message`. Does NOT touch `last_transaction_id` or
    `last_position` — retry semantics are preserved by leaving the
    cursor where it was.

    Truncates `error_message` to 500 chars to bound bookmark UPDATE
    size. If this UPDATE itself fails, the worker swallows that loss
    silently: we already failed once; the operator's signal is the
    log + (eventually) OTel span on the original failure.
    """
    truncated = error_message[:_ERROR_MESSAGE_MAX_CHARS]
    async with pool.acquire() as conn:
        await conn.execute(_WRITE_BOOKMARK_FAILURE_SQL, name, truncated)


__all__ = [
    "MissingBookmarkError",
    "read_bookmark",
    "write_bookmark",
    "write_bookmark_failure",
]
