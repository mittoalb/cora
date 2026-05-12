"""Projection Protocol + the internal Subscriber primitive it satisfies.

`Projection` is the public concept users write per BC. `Subscriber` is
the framework-internal primitive the worker advances along the event
stream; today every Subscriber is a Projection. Future sagas / external
adapters land as additional Protocols satisfying Subscriber, sharing
the same advance machinery without duplicating it.

The Protocols are structurally identical right now (same field set,
same callable shape). The split is intentional: it documents the
extensibility seam without surfacing two concepts to BC authors. When
a saga framework lands, the worker iterates `Subscriber`-shaped
objects regardless of whether they happen to be Projections or Sagas.
"""

from typing import Any, Protocol, runtime_checkable

from cora.infrastructure.ports.event_store import StoredEvent

# `Any` for the connection argument because asyncpg's `pool.acquire()`
# yields `PoolConnectionProxy`, not `Connection` directly, and pyright
# narrows the union loosely. The proxy delegates to Connection at
# runtime so the interface (.execute / .fetch / .transaction / etc.)
# behaves identically. Existing Postgres adapters in this codebase
# adopt the same pattern.
ConnectionLike = Any


@runtime_checkable
class Subscriber(Protocol):
    """Internal framework primitive: anything the projection worker
    advances along the event stream via a bookmark.

    Not exported publicly. Today every Subscriber is a Projection;
    future sagas / external adapters will satisfy this Protocol too.

    `name` and `subscribed_event_types` are declared as plain attrs
    (not ClassVar) so test fixtures can construct varying instances
    inline. Production projections typically declare them as
    `ClassVar` constants at the class level since they're immutable
    per projection — that satisfies this Protocol via structural
    typing.
    """

    name: str
    subscribed_event_types: frozenset[str]

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None: ...


@runtime_checkable
class Projection(Protocol):
    """Read-side fold of an event stream into a queryable `proj_*` table.

    A BC's projection lives at `cora.<bc>.projections.<name>` and is
    registered via `register_<bc>_projections(registry, deps)`. The
    framework owns advance, bookmarking, and at-least-once delivery;
    the projection owns the `apply` logic and the schema of its
    `proj_<bc>_<name>` table.

    Contract:

      - `name` MUST match the projection's `proj_*` table name AND
        the bookmark row inserted in the projection's migration.
        This is the key the worker uses to look up the bookmark
        (`projection_bookmarks.name = self.name`) and the convention
        that lets the arch-fitness test verify the registration ↔
        migration ↔ bookmark all line up.

      - `subscribed_event_types` is the set of `event_type` strings the
        projection cares about. The advance query pushes the predicate
        down to SQL (`event_type = ANY($subscribed)`); events outside
        the set are never delivered to `apply`.

      - `apply` MUST be idempotent. The framework delivers at-least-
        once: under crash-restart between `apply()` and bookmark
        update, the next batch will re-deliver the event. Standard
        patterns: `INSERT ... ON CONFLICT (key) DO NOTHING/UPDATE`,
        UPDATE-to-same-value, or any operation whose net effect is
        independent of how many times it runs. The arch-fitness test
        scans every projection's `apply` source for an idempotency
        marker (an `ON CONFLICT` substring or an explicit
        `# idempotent: <reason>` comment).

      - `apply` runs INSIDE the worker's advance transaction. The
        bookmark advance + the projection writes commit together;
        if `apply` raises, the entire batch rolls back and the
        bookmark stays at its previous position so the same events
        are retried on the next iteration.

      - The connection passed to `apply` is the same connection the
        worker uses for the advance scan and the bookmark UPDATE.
        Don't acquire your own connection from the pool; use the one
        you're given.

    Operational notes:

      - Long-running transactions in the same database PAUSE all
        projections (`pg_snapshot_xmin` returns the lowest active
        xid8; events from later-started transactions become visible
        to projections only after the long transaction commits). By
        design — operational mode worth knowing. Avoid `BEGIN;` in
        psql sessions while debugging projection lag.

      - The advance query orders by `(transaction_id, position)` so
        events appear in commit order across streams. Within a single
        transaction (one xid8 covering N events), order is by
        position.

      - Per-projection bookmarks mean projections advance independently
        and at their own pace. One projection lagging does not block
        others.
    """

    name: str
    subscribed_event_types: frozenset[str]

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        """Apply a single event to the projection's read-model state.

        Idempotency is the projection author's responsibility; the
        framework will re-deliver under at-least-once semantics.
        """
        ...


__all__ = ["ConnectionLike", "Projection", "Subscriber"]
