-- Phase audit-2026-05-20 Iter C-1: build Agent BC's first projection
-- (Path C — additive step before Iter C-2 removes the duplicated
-- state-side timestamps on the Agent aggregate).
--
-- Agent BC shipped 8f-a yesterday with `defined_at` / `versioned_at`
-- / `deprecated_at` materialized directly on aggregate state — the
-- drift the audit-2026-05-20 surfaced. Path C lock: state stays
-- decider-minimal; lifecycle timestamps live on the projection.
-- Iter A piloted on Method, Iter B replicated to Plan/Practice/
-- Family/Capability (the 5 aggregates that already had projections);
-- Iter C-1 brings Agent up to the same shape by building the
-- previously-absent `proj_agent_summary` table + projection.
-- Iter C-2 then removes the duplicated state-side timestamps.
--
-- Subscribed events: AgentDefined / AgentVersioned / AgentDeprecated.
-- Suspended/Resumed are FSM-extensions (8f-c iter 2) — those
-- timestamps stay on state for now because the decider reads them
-- (`suspension_reason` is invariant-bearing); they don't fall under
-- the audit's "derivable / decider-doesn't-read" criterion.
--
-- Mutable read model. cora_app gets full DML. Bookmark seeded so the
-- projection worker advances from genesis on first run.

CREATE TABLE proj_agent_summary (
    agent_id       UUID        PRIMARY KEY,
    kind           TEXT        NOT NULL,
    name           TEXT        NOT NULL,
    version        TEXT        NOT NULL,
    status         TEXT        NOT NULL CHECK (
        status IN ('Defined', 'Versioned', 'Suspended', 'Deprecated')
    ),
    created_at     TIMESTAMPTZ NOT NULL,
    versioned_at   TIMESTAMPTZ,
    deprecated_at  TIMESTAMPTZ,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX proj_agent_summary_keyset_idx
    ON proj_agent_summary (created_at, agent_id);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_agent_summary TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_agent_summary')
ON CONFLICT DO NOTHING;
