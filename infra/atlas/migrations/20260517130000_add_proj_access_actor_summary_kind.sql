-- Phase 8f-a: expose `Actor.kind` on the Access BC read surface.
--
-- The Agent BC at 8f-a co-writes `ActorRegistered(kind="agent")` +
-- `AgentDefined` in one transaction via `EventStore.append_streams`;
-- the design-memo's load-bearing claim is that `Decision.actor_id`
-- references resolve uniformly to either a human or an agent Actor.
-- Without `kind` on the projection, consumers cannot distinguish the
-- two at query time.
--
-- Additive forward-only migration:
--   - `kind text NOT NULL DEFAULT 'human'` so existing rows backfill
--     to `human` (matches the in-memory `ActorKind.HUMAN` default + the
--     `from_stored` forward-compat fold of pre-8f-a `ActorRegistered`
--     payloads that lacked `kind`).
--   - CHECK constraint catches typos in the projection code (mirror of
--     the existing `status` CHECK pattern).
--
-- The projection's `apply()` for `ActorRegistered` is updated in the
-- same commit (`cora.access.projections.summary._INSERT_ACTOR_SQL`) to
-- write `kind = payload.get("kind", "human")`.

ALTER TABLE proj_access_actor_summary
    ADD COLUMN kind TEXT NOT NULL DEFAULT 'human'
        CHECK (kind IN ('human', 'agent'));
