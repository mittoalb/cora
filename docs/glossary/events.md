# Event sourcing terms

*Event store, streams, positions, transactions, projections.*

- **Event store.** Append-only Postgres table of immutable events. INSERT-only at the DB role level.
- **Stream.** All events for one aggregate instance, ordered by version.
- **Position.** Global monotonic ordinal of an event in the store.
- **transaction_id (xid8).** PG18 transaction identifier on every event. Lets projection workers advance a cursor without skipping in-flight inserts.
- **Projection.** A read model built by replaying events into a denormalized table. Workers tail the store and advance a bookmark.
