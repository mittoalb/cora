# Data

For implementers picking storage and migration tools. Each row names a role, the current pick, the reason, and the trigger that would force a swap.

## Storage

| Role | Pick | Why | Swap trigger |
| --- | --- | --- | --- |
| Relational store | Postgres 18 | Single store for events + projections + idempotency + vectors; PG18 AIO ~3× faster for projection reads | Multi-tenant scale-out, or workload justifying a true streaming store (NATS, Kafka) |
| Event store | Hand-rolled `events` table | Total control of envelope, role-level immutability, transaction-id cursor | Dedicated product (EventStoreDB, Marten) only when features outweigh lock-in |
| Vector index | pgvector | Same store; sufficient for Decision-BC embeddings | Throughput or recall past pgvector's envelope |

## Migration

| Role | Pick | Why | Swap trigger |
| --- | --- | --- | --- |
| Schema migration | Atlas | Hash-verified directory, forward-only, CI-friendly | Atlas's licence model becoming a problem |
