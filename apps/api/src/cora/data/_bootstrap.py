"""Data BC lifespan bootstrap: default storage Supply + Distribution backfill.

Two lifespan-Python startup steps per [[project-data-distribution-design]]
Slice 2 (L23 + L23a + L24 + L24a + L24b):

  1. `bootstrap_default_storage_supply(kernel)`: resolves
     `Settings.self_facility_default_storage_supply_code` against
     `proj_supply_summary`. Fail-loud on env-var-unset-with-legacy-
     Datasets, missing Supply, wrong kind, or non-Available status
     (4 L23a error classes). Returns the resolved `supply_id` or
     `None` when env var is unset AND no legacy Datasets need
     backfill.

  2. `bootstrap_distribution_backfill(kernel, supply_id)`: under a
     Postgres advisory lock, INSERTs one `proj_data_distribution_summary`
     row per legacy Dataset that lacks a backfilled Distribution.
     Returns the row count. No-op when `supply_id is None`.

Both run at lifespan startup AFTER `bootstrap_federation` and BEFORE
projection workers register and BEFORE the REST `yield`. Atlas CLI
runs as a separate process and cannot read session-local GUCs set by
app lifespan, so the original SQL+GUC backfill mechanism was rejected
in favor of runtime-Python.

## Re-export retained

`SYSTEM_PRINCIPAL_ID` is re-exported for the legacy import path used
by Data's MCP tools (`cora.data._bootstrap.SYSTEM_PRINCIPAL_ID`).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from urllib.parse import urlparse
from uuid import UUID, uuid5

from cora.data.aggregates.dataset import load_dataset
from cora.data.aggregates.distribution import (
    DefaultStorageSupplyCodeUnsetError,
    DefaultStorageSupplyKindMismatchError,
    DefaultStorageSupplyNotAvailableError,
    DefaultStorageSupplyNotFoundError,
    UnmappedDistributionUriSchemeError,
)
from cora.data.aggregates.distribution._namespaces import (
    _DATA_DISTRIBUTION_BACKFILL_NAMESPACE,  # pyright: ignore[reportPrivateUsage]
)
from cora.data.aggregates.distribution.state import (
    STORAGE_SUPPLY_KIND,
    URI_SCHEME_TO_ACCESS_PROTOCOL,
)
from cora.infrastructure.logging import get_logger
from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel

_log = get_logger(__name__)

# Fixed 64-bit key used by `pg_advisory_lock` / `pg_advisory_unlock`
# to serialize concurrent multi-worker Distribution-backfill startups.
# Per L23: keyed conceptually on `proj_data_distribution_summary` (the
# only table the backfill writes); the literal integer is the first
# 8 bytes of `_DATA_DISTRIBUTION_BACKFILL_NAMESPACE` reinterpreted as
# a signed bigint, computed once at import time. Stable across boots
# without depending on the table's runtime OID (which differs per
# database). Lock id is process-wide; held only for the duration of
# the backfill INSERT loop.
_BACKFILL_ADVISORY_LOCK_ID: int = int.from_bytes(
    _DATA_DISTRIBUTION_BACKFILL_NAMESPACE.bytes[:8], "big", signed=True
)


async def bootstrap_default_storage_supply(kernel: Kernel) -> UUID | None:
    """Resolve the default storage Supply for the Distribution backfill.

    Reads `Settings.self_facility_default_storage_supply_code`; resolves
    against `proj_supply_summary` by `name` column (Supply BC's
    operator-readable identifier; there is no separate `code` column).

    Returns the resolved `supply_id` (UUID), or `None` when the env var
    is unset AND no legacy Datasets exist (clean install no-op).

    Fail-loud branches per L23a:
      - env unset + legacy Datasets exist -> DefaultStorageSupplyCodeUnsetError
      - env set + Supply missing          -> DefaultStorageSupplyNotFoundError
      - resolved kind != "Storage"        -> DefaultStorageSupplyKindMismatchError
      - resolved status != "Available"    -> DefaultStorageSupplyNotAvailableError

    Pool-less / in-memory deployments short-circuit cleanly (`kernel.pool
    is None`) and return `None`; the backfill step that follows is also
    a no-op without a pool.
    """
    pool = kernel.pool
    if pool is None:
        _log.info("default_storage_supply.skipped_no_pool")
        return None

    supply_code = kernel.settings.self_facility_default_storage_supply_code

    async with pool.acquire() as conn:
        legacy_count: int = await conn.fetchval("SELECT COUNT(*) FROM proj_data_dataset_summary")

        if supply_code is None:
            if legacy_count > 0:
                raise DefaultStorageSupplyCodeUnsetError(legacy_count)
            _log.info("default_storage_supply.no_default_storage_supply_required")
            return None

        row = await conn.fetchrow(
            "SELECT supply_id, kind, status FROM proj_supply_summary WHERE name = $1 LIMIT 1",
            supply_code,
        )

    if row is None:
        raise DefaultStorageSupplyNotFoundError(supply_code)

    actual_kind: str = row["kind"]
    actual_status: str = row["status"]
    supply_id: UUID = row["supply_id"]

    if actual_kind != STORAGE_SUPPLY_KIND:
        raise DefaultStorageSupplyKindMismatchError(supply_code, actual_kind)
    if actual_status != "Available":
        raise DefaultStorageSupplyNotAvailableError(supply_code, actual_status)

    _log.info(
        "default_storage_supply.resolved",
        supply_code=supply_code,
        supply_id=str(supply_id),
    )
    return supply_id


async def bootstrap_distribution_backfill(kernel: Kernel, supply_id: UUID | None) -> int:
    """Backfill `proj_data_distribution_summary` from legacy Dataset rows.

    No-op when `supply_id is None` (clean install or pool-less env).

    For every Dataset in `proj_data_dataset_summary` that lacks a
    backfilled Distribution row, loads the Dataset's event stream to
    recover the byte-identical-copy fields (checksum, byte_size,
    encoding) and the genesis attribution (registered_by): these
    fields live on the genesis event payload, not the Dataset
    summary projection. Then maps the URI scheme to an `AccessProtocol`
    via the closed `URI_SCHEME_TO_ACCESS_PROTOCOL` lookup. Unmapped
    schemes abort the entire backfill via `UnmappedDistributionUriSchemeError`.

    The deterministic `distribution_id = uuid5(_DATA_DISTRIBUTION_BACKFILL_NAMESPACE,
    str(dataset_id))` derivation per L24a means re-running the backfill
    on a freshly-rebuilt projection produces identical ids; the
    `ON CONFLICT (distribution_id) DO NOTHING` clause makes the backfill
    idempotent across re-runs (and races with a stray native
    DistributionRegistered event that happened to derive the same
    deterministic id, per L24b).

    Returns the count of rows inserted on this run.
    """
    if supply_id is None:
        return 0
    pool = kernel.pool
    if pool is None:
        _log.info("distribution_backfill.skipped_no_pool")
        return 0

    inserted = 0

    async with pool.acquire() as conn:
        await conn.execute("SELECT pg_advisory_lock($1)", _BACKFILL_ADVISORY_LOCK_ID)
        try:
            pending_rows = await conn.fetch(
                "SELECT dataset_id, uri, created_at "
                "FROM proj_data_dataset_summary "
                "WHERE dataset_id NOT IN ("
                "    SELECT dataset_id FROM proj_data_distribution_summary "
                "    WHERE backfilled = TRUE"
                ") "
                "ORDER BY dataset_id"
            )

            for row in pending_rows:
                dataset_id: UUID = row["dataset_id"]
                uri: str = row["uri"]
                created_at = row["created_at"]

                scheme = urlparse(uri).scheme.lower()
                access_protocol = URI_SCHEME_TO_ACCESS_PROTOCOL.get(scheme)
                if access_protocol is None:
                    raise UnmappedDistributionUriSchemeError(uri, scheme)

                # Load the Dataset event stream once: the folded Dataset
                # carries the byte-identical-copy fields (checksum, byte_size,
                # encoding) the backfill needs; the genesis event payload
                # carries the `registered_by` actor id (not denormalized on
                # the Dataset state per fold-NEITHER convention).
                stored_events, _version = await kernel.event_store.load("Dataset", dataset_id)
                if not stored_events:
                    # Projection row exists but event stream is missing:
                    # corrupted DB; skip with WARN.
                    _log.warning(
                        "distribution_backfill.dataset_stream_missing",
                        dataset_id=str(dataset_id),
                    )
                    continue
                dataset = await load_dataset(kernel.event_store, dataset_id)
                if dataset is None:
                    _log.warning(
                        "distribution_backfill.dataset_fold_returned_none",
                        dataset_id=str(dataset_id),
                    )
                    continue
                registered_by = UUID(stored_events[0].payload["registered_by"])

                distribution_id = uuid5(_DATA_DISTRIBUTION_BACKFILL_NAMESPACE, str(dataset_id))

                checksum_jsonb = json.dumps(
                    {
                        "algorithm": dataset.checksum.algorithm,
                        "value": dataset.checksum.value,
                    }
                )
                encoding_jsonb = json.dumps(
                    {
                        "media_type": dataset.encoding.media_type,
                        "conforms_to": sorted(dataset.encoding.conforms_to),
                    }
                )

                result = await conn.execute(
                    "INSERT INTO proj_data_distribution_summary "
                    "(distribution_id, dataset_id, supply_id, uri, "
                    " checksum, byte_size, encoding, access_protocol, "
                    " status, registered_at, registered_by, backfilled) "
                    "VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7::jsonb, $8, "
                    "        'Registered', $9, $10, TRUE) "
                    "ON CONFLICT (distribution_id) DO NOTHING",
                    distribution_id,
                    dataset_id,
                    supply_id,
                    dataset.uri.value,
                    checksum_jsonb,
                    dataset.byte_size,
                    encoding_jsonb,
                    access_protocol.value,
                    created_at,
                    registered_by,
                )
                if result.endswith(" 1"):
                    inserted += 1
        finally:
            await conn.execute("SELECT pg_advisory_unlock($1)", _BACKFILL_ADVISORY_LOCK_ID)

    _log.info(
        "distribution_backfill.complete",
        count=inserted,
        supply_id=str(supply_id),
    )
    return inserted


__all__ = [
    "SYSTEM_PRINCIPAL_ID",
    "bootstrap_default_storage_supply",
    "bootstrap_distribution_backfill",
]
