"""`drain_projections`: integration-test helper.

Synchronously advances every registered projection until each
bookmark catches up to the head event position, OR raises
`ProjectionDrainTimeoutError` if the deadline elapses first.

Lets contract / integration tests assert against projection state
immediately after appending events without sprinkling
`asyncio.sleep(...)` and hoping. Also serves as the documented
escape hatch for in-process workflows that need synchronous
projection consistency (rare; should not become a regular pattern).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import asyncio

import asyncpg

from cora.infrastructure.projection.registry import ProjectionRegistry
from cora.infrastructure.projection.worker import advance_subscriber_once

_HEAD_POSITION_SQL = "SELECT COALESCE(MAX(position), 0) FROM events"

_BOOKMARK_POSITION_SQL = """
SELECT last_position FROM projection_bookmarks WHERE name = $1
"""


class ProjectionDrainTimeoutError(Exception):
    """Raised when `drain_projections` exceeds its deadline before all
    bookmarks catch up. Indicates a stuck projection (apply() raising
    on every retry, or events landing faster than the test can drain
    them)."""

    def __init__(
        self,
        *,
        deadline_seconds: float,
        head_position: int,
        bookmarks: dict[str, int],
    ) -> None:
        super().__init__(
            f"drain_projections did not catch up within {deadline_seconds}s. "
            f"Head position: {head_position}; bookmarks: {bookmarks}"
        )
        self.deadline_seconds = deadline_seconds
        self.head_position = head_position
        self.bookmarks = bookmarks


async def drain_projections(
    pool: asyncpg.Pool,
    registry: ProjectionRegistry,
    *,
    deadline_seconds: float = 5.0,
    batch_size: int = 100,
) -> None:
    """Advance every registered projection until all bookmarks reach
    the head event position, or the deadline expires.

    The head position is sampled once per outer loop iteration; if
    new events land mid-drain, they're caught on the next sample.
    """
    if registry.is_empty():
        return

    loop = asyncio.get_event_loop()
    deadline = loop.time() + deadline_seconds

    while True:
        async with pool.acquire() as conn:
            head_position: int = int(await conn.fetchval(_HEAD_POSITION_SQL))
            bookmarks: dict[str, int] = {}
            for projection in registry:
                row = await conn.fetchval(_BOOKMARK_POSITION_SQL, projection.name)
                bookmarks[projection.name] = int(row) if row is not None else 0

        if all(pos >= head_position for pos in bookmarks.values()):
            return

        if loop.time() >= deadline:
            raise ProjectionDrainTimeoutError(
                deadline_seconds=deadline_seconds,
                head_position=head_position,
                bookmarks=bookmarks,
            )

        # Advance every behind projection by one batch in parallel.
        await asyncio.gather(
            *[
                advance_subscriber_once(pool, projection, batch_size=batch_size)
                for projection in registry
                if bookmarks[projection.name] < head_position
            ]
        )


__all__ = ["ProjectionDrainTimeoutError", "drain_projections"]
