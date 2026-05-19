-- Phase C Iter B-2: widen `proj_access_actor_summary.kind` CHECK
-- to add `service_account`.
--
-- Original migration (20260517130000) pinned `kind IN ('human', 'agent')`.
-- Iter B-2 widens the `ActorKind` StrEnum to include `service_account`
-- (machine callers: CI bridges, autonomous agent runtime processes,
-- future TomoScan/EPICS bridges). Without this CHECK update, the
-- projection writer would fail to insert any new service-account
-- Actor row.
--
-- Forward-only per project_forward_only_migrations memory. The
-- DROP CONSTRAINT + ADD CONSTRAINT pair is the standard PG idiom for
-- widening a CHECK; both are metadata-only on PG 11+ (no table scan)
-- because the new set is a STRICT SUPERSET of the old set — every
-- existing row's `kind` value is still permitted.
--
-- Atlas safety: ALTER TABLE ... DROP CONSTRAINT + ADD CONSTRAINT are
-- not on Atlas's forbidden-DDL list. No `--atlas:nolint` opt-out
-- needed.

ALTER TABLE proj_access_actor_summary
    DROP CONSTRAINT proj_access_actor_summary_kind_check;

ALTER TABLE proj_access_actor_summary
    ADD CONSTRAINT proj_access_actor_summary_kind_check
        CHECK (kind IN ('human', 'agent', 'service_account'));
