"""EventPublisher port: notify downstream subscribers of newly appended events.

Default Phase 1b adapter uses Postgres `LISTEN/NOTIFY` driven by an
`AFTER INSERT` trigger on the events table. Future trigger (per
project_deferred.md): swap to NATS JetStream when cross-process workers,
durable replay outside main DB retention, or multi-region federation arise.
The swap is local to one infrastructure file; domain and application code
unaffected.
"""

from typing import Protocol

from cora.infrastructure.ports.event_store import StoredEvent


class EventPublisher(Protocol):
    """Notify downstream subscribers of newly persisted events.

    Append-and-publish atomicity is the responsibility of the EventStore
    adapter (typically via a transactional outbox row or a database trigger).
    The publisher's job is to deliver the notification to subscribers.
    """

    async def publish(self, events: list[StoredEvent]) -> None: ...
