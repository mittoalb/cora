# State

*Envelope, invariants, read models.*

Every state change emits immutable events; aggregate state is folded from the stream. Mechanism below is Postgres-specific; for the storage pick itself, see [Stack/Data](../stack/data.md).

## Envelope

Every event lands in `events` with a typed envelope wrapping a primitives-only payload. The envelope carries identity, ordering, and audit; the payload carries the change.

```json
{
  "event_id": "01900000-...",      // UUIDv7, dedup key
  "stream_id": "01900000-...",     // aggregate id
  "stream_type": "actor",
  "event_type": "ActorRegistered",
  "version": 1,                    // per-stream monotonic
  "position": 42,                  // global monotonic
  "transaction_id": "12345678",    // PG xid8 for projection cursor
  "principal_id": "01900000-...",  // who emitted (ReBAC hook)
  "occurred_at": "2026-05-13T14:00:00Z",
  "payload": { "actor_id": "...", "name": "Doga" }
}
```

Subscribers route on `(stream_type, event_type)` and dedupe on `event_id`.

## Invariants

- **Append-only by DB role.** App role: SELECT + INSERT only; UPDATE/DELETE/TRUNCATE revoked. Immutability enforced by Postgres, not by convention.
- **Gap-free ordering by transaction id.** Each event carries its committing PG `xid8`. Projection workers advance against committed transactions, never skipping in-flight inserts.
- **Optimistic concurrency by `version`.** Writers assert the expected per-stream version on append; a mismatch fails the transaction. No advisory locks, no last-write-wins.

## Read models

- **Fold-on-read.** Single-aggregate `GET` replays its stream every read. No snapshots yet.
- **Projection workers.** List, filter, search. Background processes tail `events`, advance a per-projection `xid8` bookmark, maintain denormalised tables. Framework is generic; per-projection logic plugs in via a registry.
