-- Phase 6f-5b: per-Run sensor / motor reading entry table.
--
-- Third concrete entry category in CORA after entries_conduit_traversals
-- (6f-5a) and entries_decision_reasonings (8c-b). Each row captures one
-- reading recorded against a Run (sensor sample, motor position, etc.)
-- via its `reading` logbook (RunReadingLogbookOpened on the Run stream,
-- kind=LOGBOOK_KIND_READING).
--
-- ## Storage strategy: polymorphic-with-discriminator
--
-- Unlike the prior two entry kinds (typed-per-category), this table is
-- POLYMORPHIC across reading kinds (baseline, monitor, future primary /
-- triggered) with the W3C SOSA 2023 `sosa:samplingProcedure`
-- discriminator carried as the `sampling_procedure` column. The OGC
-- ISO 19156:2023 OMS criterion: typed specialisation only when the
-- value-column shape diverges. All RunReading kinds share the SAME
-- `(channel_name, value, units?, sampled_at)` shape, so a single table
-- with a discriminator is the standards-converged choice.
--
-- See [[project_logbook_entry_storage]] for the cross-BC formulation
-- of the typed-vs-polymorphic decision rule.
--
-- ## Closed enum at the API layer, not in DDL
--
-- `sampling_procedure` is plain TEXT; the closed enum
-- (Literal["baseline"] in 6f-5b, +"monitor" in 6f-5c, future-additive)
-- is enforced at Pydantic at the API boundary. CHECK-constraint enums
-- in DDL would couple every operational vocabulary extension to a
-- migration. (Compare to entries_conduit_traversals.decision which IS
-- a CHECK enum because Allow/Deny is a domain invariant; sampling
-- procedures are operational vocabulary that grows.)
--
-- ## Three timestamps
--
--   - sampled_at: SOSA phenomenonTime — when the sensor captured the
--     value (mandatory; defaults to occurred_at at the API for human-
--     entered values)
--   - occurred_at: when the handler appended the entry (Clock port;
--     same convention as the events table)
--   - recorded_at: when Postgres wrote the row (DEFAULT now(); same
--     convention as the events table)
--
-- ## Why no FK to the Run aggregate
--
-- The Run lives in `events` not in its own row; FK to (stream_type,
-- stream_id) is not a standard SQL shape and would force schema coupling
-- between the two storage paths. Eventual-consistency stance: run_id
-- references whatever Run ID was passed; downstream queries can join
-- via projections. Same posture as the prior two entry tables.
--
-- ## Indexes
--
--   - PK on event_id (UNIQUE; idempotency / dedup key per the existing
--     event-sourcing convention; ON CONFLICT (event_id) DO NOTHING
--     handles producer retries silently)
--   - btree on (run_id, sampled_at DESC) — primary read pattern
--     "latest readings for this Run, paged by sensor time"
--   - btree on (run_id, sampling_procedure, sampled_at DESC) —
--     supports kind-filtered queries: "all baseline readings for Run X"
--   - btree on (logbook_id) — supports "all entries for this logbook
--     session" reads (when a logbook closes and we want to summarize)
--   - BRIN on recorded_at — supports retention sweeps and time-range
--     analytics; cheap (BRIN ~1% the size of btree); matches the
--     append-mostly access pattern. Same shape as the prior two
--     entry tables.
--
-- ## Partitioning / hypertable conversion deferred
--
-- Single table + BRIN is the right starting shape. Per the design memo
-- watch items, TimescaleDB hypertable conversion lands when row counts
-- cross ~10^7 (TimescaleDB itself is in [[project_deferred]]).

CREATE TABLE entries_run_readings (
    event_id            uuid              PRIMARY KEY,
    run_id              uuid              NOT NULL,
    logbook_id          uuid              NOT NULL,
    actor_id            uuid              NOT NULL,
    command_name        text              NOT NULL,
    channel_name        text              NOT NULL CHECK (length(channel_name) BETWEEN 1 AND 255),
    -- Defense-in-depth: NaN and Infinity rejected at write time. The
    -- Pydantic API layer ALSO enforces this via allow_inf_nan=False,
    -- and the in-decider InvalidReadingValueError covers direct callers
    -- that bypass Pydantic. Three layers; matches the bounded-text
    -- constraint pattern across the codebase.
    value               double precision  NOT NULL CHECK (
        value = value
        AND value <> 'Infinity'::double precision
        AND value <> '-Infinity'::double precision
    ),
    units               text              CHECK (units IS NULL OR length(units) <= 64),
    sampling_procedure  text              NOT NULL,
    sampled_at          timestamptz       NOT NULL,
    occurred_at         timestamptz       NOT NULL,
    correlation_id      uuid              NOT NULL,
    causation_id        uuid,
    recorded_at         timestamptz       NOT NULL DEFAULT now()
);

CREATE INDEX entries_run_readings_run_sampled_idx
    ON entries_run_readings (run_id, sampled_at DESC);

CREATE INDEX entries_run_readings_run_procedure_sampled_idx
    ON entries_run_readings (run_id, sampling_procedure, sampled_at DESC);

CREATE INDEX entries_run_readings_logbook_idx
    ON entries_run_readings (logbook_id);

CREATE INDEX entries_run_readings_recorded_at_brin_idx
    ON entries_run_readings USING BRIN (recorded_at);

-- Append-only at the role level (project_immutability_guarantee.md):
-- the cora_app role gets SELECT + INSERT via ALTER DEFAULT PRIVILEGES
-- in 20260512230000_init_role_cora_app.sql; this REVOKE explicitly
-- removes UPDATE / DELETE / TRUNCATE so a future migration cannot
-- accidentally re-grant them. Mirrors the precedent set by the prior
-- two entry tables (entries_conduit_traversals, entries_decision_reasonings).
REVOKE UPDATE, DELETE, TRUNCATE ON entries_run_readings FROM cora_app;
