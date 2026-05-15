-- Phase 11a-b cleanup: partial UNIQUE INDEX on (kind, external_id).
--
-- Promoted from `[gap]` watch item #16 in [[project_safety_clearance_design]],
-- which anticipated this trigger ("11a-b projection lands"). Without the
-- index, two Clearances with the same facility-minted regulatory ID
-- (e.g., ESAF-12345) sit silently in the read model; downstream
-- lookup-by-external-id queries return ambiguous rows. Pure additive at
-- projection-creation time; cheap insurance.
--
-- Partial-index predicate `WHERE external_id IS NOT NULL` keeps the
-- uniqueness scoped to clearances that HAVE a facility-minted id
-- (lazy-mint pattern from PID landscape: external_id is NULL until the
-- facility approves + assigns). Multiple pre-mint clearances with
-- NULL external_id remain allowed.
--
-- `(kind, external_id)` is the right key shape, not bare `(external_id)`:
-- two different facility forms can in principle share an external-id
-- namespace (unlikely in practice but defensible by the cross-facility
-- portability research; APS ESAF and NSLS-II PASS use disjoint number
-- spaces today, but a future facility-acquisition might collapse them).

CREATE UNIQUE INDEX proj_safety_clearance_summary_external_id_unique_idx
    ON proj_safety_clearance_summary (kind, external_id)
    WHERE external_id IS NOT NULL;
