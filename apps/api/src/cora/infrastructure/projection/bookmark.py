"""Bookmark read/write SQL helpers.

The worker's advance loop calls these inside its transaction:

  1. `read_bookmark(conn, name)` -> `(last_transaction_id, last_position)`
     locks the bookmark row FOR UPDATE so concurrent workers (when
     deferred multi-worker arrives) won't double-advance.
  2. `write_bookmark(conn, name, last_tx, last_pos)` updates the
     bookmark; commits with the same transaction as the projection
     writes for atomic at-least-once delivery.

Bookmark rows are created by per-projection migrations (`INSERT INTO
projection_bookmarks (name) VALUES (...) ON CONFLICT DO NOTHING`),
not by the worker — registering a projection without its migration
having landed will fail loudly at first advance, which is the
behavior we want.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from cora.infrastructure.projection.handler import ConnectionLike

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
SET last_transaction_id = $2::xid8,
    last_position       = $3,
    updated_at          = now()
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
) -> None:
    """Update the bookmark to the new (last_tx, last_pos) cursor."""
    await conn.execute(
        _WRITE_BOOKMARK_SQL,
        name,
        last_transaction_id,
        last_position,
    )


__all__ = ["MissingBookmarkError", "read_bookmark", "write_bookmark"]
