-- Phase 10c-b: per-Procedure step entry table.
--
-- Fourth concrete entry category in CORA after entries_conduit_traversals
-- (6f-5a), entries_decision_reasonings (8c-b), and entries_run_readings
-- (6f-5b). Each row captures one procedural step recorded against a
-- Procedure (Setpoint applied, Action performed, Check verified) via its
-- `steps` logbook (ProcedureStepsLogbookOpened on the Procedure stream,
-- kind=LOGBOOK_KIND_STEPS).
--
-- ## Storage strategy: polymorphic-with-discriminator + JSON payload
--
-- The three step kinds (setpoint / action / check) are CORA's rename of
-- ISA-106's canonical Command/Perform/Verify triplet (renamed to avoid
-- catastrophic collision with CQRS Command per [[project_operation_design]]).
-- Their per-kind payload shapes diverge: a setpoint has channel + target_value
-- + units + ramp_rate; an action has action_name + params; a check has
-- channel + passed + expected + actual + tolerance. Per
-- [[project_logbook_entry_storage]]'s typed-vs-polymorphic decision rule,
-- shape divergence usually drives the typed-per-category split.
--
-- The 10c design memo nonetheless locked polymorphic-with-discriminator
-- (single table, kind discriminator + JSON `payload`) for two reasons:
--
--   1. Mirror 6f-5b RunReading exactly to keep the substream pattern
--      uniform across Run-side and Procedure-side timelines (operators
--      learn one shape, tooling reads one shape).
--   2. Step shape is operational vocabulary that will EVOLVE during the
--      pilot (ramp_rate today, ramp_profile tomorrow, kind-specific
--      retry policy later). A typed-per-kind table-split locks the
--      column shape per kind; JSON payload lets the per-kind contract
--      live in code (Pydantic at the API boundary) and evolve without
--      migrations. Same posture as OpenTelemetry events (name + JSON
--      attributes) and AAS TimeSeriesData payloads.
--
-- The watch item "step atom split" in [[project_operation_design]] sets
-- the trigger for a future sibling-table refactor: when ad-hoc per-kind
-- analytical queries fire OR when one kind crosses ~10^7 rows OR when a
-- 4th kind family lands.
--
-- ## Closed enum at the API layer, not in DDL
--
-- `step_kind` is plain TEXT; the closed enum (Literal["setpoint",
-- "action", "check"] in 10c-b, future-additive) is enforced at Pydantic
-- at the API boundary. Same posture as entries_run_readings.sampling_procedure.
--
-- ## Three timestamps
--
--   - sampled_at: phenomenonTime — when the step physically happened in
--     the field (operator-recorded or instrument-clock; mandatory)
--   - occurred_at: when the handler appended the entry (Clock port;
--     same convention as the events table)
--   - recorded_at: when Postgres wrote the row (DEFAULT now(); same
--     convention as the events table)
--
-- ## Why no FK to the Procedure aggregate
--
-- Same rationale as the prior three entry tables: aggregates live in
-- the events table, not in their own row; FK to (stream_type, stream_id)
-- is non-standard SQL and would force schema coupling. Eventual-
-- consistency stance: procedure_id references whatever Procedure id was
-- passed; downstream queries can join via projections.
--
-- ## Indexes
--
--   - PK on event_id (UNIQUE; idempotency / dedup key per the existing
--     event-sourcing convention; ON CONFLICT (event_id) DO NOTHING
--     handles producer retries silently)
--   - btree on (procedure_id, sampled_at DESC) — primary read pattern
--     "latest steps for this Procedure, paged by sample time"
--   - btree on (procedure_id, step_kind, sampled_at DESC) — supports
--     kind-filtered queries: "all check steps for Procedure X"
--   - btree on (logbook_id) — supports "all entries for this logbook
--     session" reads (when a logbook closes and we want to summarize)
--   - BRIN on recorded_at — supports retention sweeps and time-range
--     analytics; cheap (BRIN ~1% the size of btree); matches the
--     append-mostly access pattern. Same shape as the prior three
--     entry tables.

CREATE TABLE entries_operation_procedure_steps (
    event_id            uuid              PRIMARY KEY,
    procedure_id        uuid              NOT NULL,
    logbook_id          uuid              NOT NULL,
    actor_id            uuid              NOT NULL,
    command_name        text              NOT NULL,
    step_kind           text              NOT NULL,
    payload             jsonb             NOT NULL,
    sampled_at          timestamptz       NOT NULL,
    occurred_at         timestamptz       NOT NULL,
    correlation_id      uuid              NOT NULL,
    causation_id        uuid,
    recorded_at         timestamptz       NOT NULL DEFAULT now()
);

CREATE INDEX entries_operation_procedure_steps_proc_sampled_idx
    ON entries_operation_procedure_steps (procedure_id, sampled_at DESC);

CREATE INDEX entries_operation_procedure_steps_proc_kind_sampled_idx
    ON entries_operation_procedure_steps (procedure_id, step_kind, sampled_at DESC);

CREATE INDEX entries_operation_procedure_steps_logbook_idx
    ON entries_operation_procedure_steps (logbook_id);

CREATE INDEX entries_operation_procedure_steps_recorded_at_brin_idx
    ON entries_operation_procedure_steps USING BRIN (recorded_at);

-- Append-only at the role level (project_immutability_guarantee.md):
-- the cora_app role gets SELECT + INSERT via ALTER DEFAULT PRIVILEGES
-- in 20260512230000_init_role_cora_app.sql; this REVOKE explicitly
-- removes UPDATE / DELETE / TRUNCATE so a future migration cannot
-- accidentally re-grant them. Mirrors the precedent set by the prior
-- three entry tables.
REVOKE UPDATE, DELETE, TRUNCATE ON entries_operation_procedure_steps FROM cora_app;
