-- Phase 6f-5a: per-Conduit authorization-traversal observation table.
--
-- The first concrete "observation" category in CORA. An observation is a
-- fine-grained record attached to a parent aggregate's main event stream
-- via a "channel" header event. The channel header (ConduitChannelOpened,
-- emitted on the Conduit's main event stream at conduit-creation) declares
-- the schema of the rows that will land in this table; the rows themselves
-- live HERE, not in the events table, because they are high-cardinality
-- (one per Authorize port call across every command in production) and
-- must not bloat the procedural log or fold into the Conduit aggregate
-- state.
--
-- Storage layout follows the gate-review L1 lock (per-category typed
-- table, not a wide-table-with-discriminator). Each future observation
-- kind (FrameTrigger, MotorPosition, ReasoningToken, etc.) gets its own
-- table with its own typed columns. Schema validation per kind, per-kind
-- index strategy, per-kind retention policy, per-kind future migration
-- to TimescaleDB if/when volume demands. Industry-validated by Tiger
-- Data's narrow-table guidance (typed columns when kinds have known
-- distinct schemas) and OpenTelemetry's per-signal storage shape.
--
-- Why no FK to the Conduit aggregate: the Conduit lives in `events` not
-- in its own row; FK to (stream_type, stream_id) is not a standard SQL
-- shape and would force schema coupling between the two storage paths.
-- Eventual-consistency stance: the conduit_id column references whatever
-- Conduit ID was passed; downstream queries can join via projections.
-- Same posture as Conduit's eventual-consistency stance for source/target
-- zone IDs.
--
-- Indexes:
--   - PK on event_id (UNIQUE, idempotency / dedup key per the existing
--     event-sourcing convention)
--   - btree on (conduit_id, occurred_at DESC) — primary read pattern is
--     "latest decisions for this Conduit, paged"
--   - btree on (channel_id) — supports "all observations for this channel
--     session" reads (e.g. when a channel closes and we want to summarize)
--   - BRIN on recorded_at — supports retention sweeps and time-range
--     analytics; cheap (BRIN is ~1% the size of btree per Crunchy Data
--     benchmarks) and matches the append-mostly access pattern
--
-- recorded_at is DB write time (compare to occurred_at = domain time
-- captured at the call site via the Clock port). Same shape as `events`.

CREATE TABLE observations_conduit_traversals (
    event_id        uuid         PRIMARY KEY,
    conduit_id      uuid         NOT NULL,
    channel_id      uuid         NOT NULL,
    actor_id        uuid         NOT NULL,
    command_name    text         NOT NULL,
    decision        text         NOT NULL CHECK (decision IN ('Allow', 'Deny')),
    reason          text,
    correlation_id  uuid         NOT NULL,
    causation_id    uuid,
    occurred_at     timestamptz  NOT NULL,
    recorded_at     timestamptz  NOT NULL DEFAULT now()
);

CREATE INDEX observations_conduit_traversals_conduit_time_idx
    ON observations_conduit_traversals (conduit_id, occurred_at DESC);

CREATE INDEX observations_conduit_traversals_channel_idx
    ON observations_conduit_traversals (channel_id);

CREATE INDEX observations_conduit_traversals_recorded_at_brin_idx
    ON observations_conduit_traversals USING BRIN (recorded_at);
