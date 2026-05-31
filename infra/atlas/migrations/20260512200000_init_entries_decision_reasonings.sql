-- Phase 8c-b: per-Decision AI-reasoning entry table.
--
-- Second concrete entry category in CORA after entries_conduit_traversals
-- (6f-5a). Each row captures one AI-decider trace event (LLM client
-- span / tool invocation / agent span) attached to a Decision aggregate
-- via its `reasoning` logbook (DecisionLogbookOpened on the Decision
-- stream, kind=LOGBOOK_KIND_REASONING).
--
-- Field set lifted from OpenTelemetry GenAI semantic conventions
-- v1.38 (2026), per the Phase 8c standards survey:
--
--   - Required NOT NULL discriminators: provider_name + operation_name
--     + request_model. Together they discriminate row shape (chat vs
--     execute_tool vs invoke_agent).
--   - Optional response identity, hyperparameters, usage counts.
--   - Optional agent context for OTel multi-agent correlation.
--   - Optional tool-call context (only populated for execute_tool ops).
--   - messages is the ONE jsonb column, carrying the OTel event
--     payload (prompt/completion bodies). Opt-in for PII gating.
--
-- Storage layout follows the per-category typed-table pattern locked
-- at gate-review L1 from 6f-5a. Per-category typed columns + per-kind
-- index strategy + per-kind future migration to TimescaleDB if/when
-- volume demands. Industry-validated by Tiger Data's narrow-table
-- guidance + OpenTelemetry's per-signal storage shape.
--
-- Why no FK to the Decision aggregate: the Decision lives in `events`
-- not in its own row; FK to (stream_type, stream_id) is not a standard
-- SQL shape and would force schema coupling between the two storage
-- paths. Eventual-consistency stance: decision_id references whatever
-- Decision ID was passed; downstream queries can join via projections.
-- Same posture as entries_conduit_traversals (6f-5a).
--
-- Indexes:
--   - PK on event_id (UNIQUE; idempotency / dedup key per the existing
--     event-sourcing convention; ON CONFLICT (event_id) DO NOTHING
--     handles producer retries silently)
--   - btree on (decision_id, occurred_at DESC) -- primary read pattern
--     "latest reasoning entries for this Decision, paged"
--   - btree on (logbook_id) -- supports "all entries for this logbook
--     session" reads (when a logbook closes and we want to summarize)
--   - btree on (conversation_id) WHERE conversation_id IS NOT NULL --
--     supports OTel multi-agent correlation queries spanning multiple
--     Decisions
--   - BRIN on recorded_at -- supports retention sweeps and time-range
--     analytics; cheap (BRIN ~1% the size of btree per Crunchy Data
--     benchmarks); matches the append-mostly access pattern
--
-- Partitioning is INTENTIONALLY deferred. Per the Phase 8c-b survey:
-- range partitioning by recorded_at becomes necessary at ~50GB table
-- size OR when retention drops/queries on time windows degrade p95
-- latency. Single table + BRIN index is the right starting shape.
-- Re-partition when the explicit thresholds fire.
--
-- recorded_at is DB write time (compare to occurred_at = domain time
-- captured at the call site via the Clock port). Same shape as `events`
-- and entries_conduit_traversals.

CREATE TABLE entries_decision_reasonings (
    event_id            uuid              PRIMARY KEY,
    decision_id         uuid              NOT NULL,
    logbook_id          uuid              NOT NULL,
    correlation_id      uuid              NOT NULL,
    causation_id        uuid,
    occurred_at         timestamptz       NOT NULL,
    duration         bigint,

    -- OTel gen_ai.* required discriminators
    operation_name      text              NOT NULL,
    provider_name       text              NOT NULL,
    request_model       text              NOT NULL,

    -- OTel gen_ai.response.* + request hyperparameters
    response_id         text,
    response_model      text,
    request_temperature double precision,
    request_top_p       double precision,
    request_max_tokens  integer,
    output_type         text,
    finish_reasons      text[],

    -- OTel gen_ai.usage.* (NOT deprecated prompt_tokens/completion_tokens)
    input_tokens        bigint,
    output_tokens       bigint,

    -- OTel gen_ai.agent.* (multi-agent correlation)
    agent_id            text,
    agent_name          text,
    agent_description   text,
    conversation_id     text,

    -- OTel gen_ai.tool.* (only for execute_tool operation)
    tool_name           text,
    tool_call_id        text,
    tool_type           text,

    -- OTel event payload (prompt/completion message bodies; PII-gated opt-in)
    messages      jsonb,

    recorded_at         timestamptz       NOT NULL DEFAULT now()
);

CREATE INDEX entries_decision_reasonings_decision_time_idx
    ON entries_decision_reasonings (decision_id, occurred_at DESC);

CREATE INDEX entries_decision_reasonings_logbook_idx
    ON entries_decision_reasonings (logbook_id);

CREATE INDEX entries_decision_reasonings_conversation_idx
    ON entries_decision_reasonings (conversation_id)
    WHERE conversation_id IS NOT NULL;

CREATE INDEX entries_decision_reasonings_recorded_at_brin_idx
    ON entries_decision_reasonings USING BRIN (recorded_at);
