-- Initial event store schema.
--
-- Single `events` table backs every aggregate stream across every BC.
-- `position` is the global commit-order watermark; `(stream_type, stream_id, version)`
-- is the per-stream optimistic-concurrency key.
--
-- An AFTER INSERT trigger fires `pg_notify('events', ...)` with a small payload
-- so listeners can wake up immediately. Notifications are best-effort and
-- non-durable: subscribers must always also poll from a persisted watermark.
-- See cora.infrastructure.ports.event_store module docstring for the
-- bigserial sequence-rollback hazard projections must handle.

CREATE TABLE events (
    position        bigserial    PRIMARY KEY,
    stream_type     text         NOT NULL,
    stream_id       uuid         NOT NULL,
    version         integer      NOT NULL CHECK (version > 0),
    event_type      text         NOT NULL,
    schema_version  integer      NOT NULL DEFAULT 1 CHECK (schema_version > 0),
    payload         jsonb        NOT NULL,
    metadata        jsonb        NOT NULL DEFAULT '{}'::jsonb,
    correlation_id  uuid         NOT NULL,
    causation_id    uuid,
    occurred_at     timestamptz  NOT NULL,
    recorded_at     timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT events_stream_version_unique
        UNIQUE (stream_type, stream_id, version)
);

-- Stream load: WHERE stream_type = $1 AND stream_id = $2 ORDER BY version.
-- The UNIQUE constraint already creates this index; named here for clarity.
CREATE INDEX events_correlation_idx ON events (correlation_id);
CREATE INDEX events_recorded_at_idx ON events (recorded_at);

CREATE OR REPLACE FUNCTION events_notify() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    PERFORM pg_notify(
        'events',
        json_build_object(
            'position',    NEW.position,
            'stream_type', NEW.stream_type,
            'stream_id',   NEW.stream_id,
            'event_type',  NEW.event_type
        )::text
    );
    RETURN NEW;
END;
$$;

CREATE TRIGGER events_notify_trigger
    AFTER INSERT ON events
    FOR EACH ROW
    EXECUTE FUNCTION events_notify();
