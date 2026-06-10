"""UUID namespace constants for Distribution-aggregate deterministic id derivation.

Per [[project-data-distribution-design]] L24a: the Slice 2 lifespan-Python
backfill derives ``Distribution.id`` from the parent ``Dataset.id`` via
``uuid5(_DATA_DISTRIBUTION_BACKFILL_NAMESPACE, str(dataset_id))``. Deterministic
so re-running the backfill on a freshly-rebuilt projection produces identical
ids (rebuild semantics per L24b).

Value is frozen at commit time and MUST never change: any future edit would
shuffle every backfilled Distribution id, and parallel rebuilds across
deployments would diverge. Treat this constant like a wire-format invariant.

Naming convention: ``_<BC>_<SCOPE>_NAMESPACE`` (private; UPPER_CASE).
Mirrors [[project-facility-aggregate-design]] ``_FEDERATION_FACILITY_NAMESPACE``
and 3 other existing CORA namespace constants per the established 4-example
grep at ``cora/agent/subscribers/`` + ``cora/safety/aggregates/`` +
``cora/federation/aggregates/``.
"""

from uuid import UUID

#: UUIDv4 chosen at first-commit time; pin for the lifetime of the BC.
#: Distinct from any other CORA namespace UUID (verified by grep).
_DATA_DISTRIBUTION_BACKFILL_NAMESPACE: UUID = UUID("01900000-0000-7000-8000-0000da7a0001")
