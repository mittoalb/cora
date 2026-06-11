"""Lifespan-bootstrap error class for the Slice 2 Distribution backfill.

Per [[project-data-distribution-design]] L23 + L23a: the Slice 2 backfill
runs as a runtime-Python lifespan step at app startup (NOT an Atlas SQL
migration, because Atlas CLI is a separate process and cannot read
session-local GUCs set by app lifespan). The bootstrap resolves the
``SELF_FACILITY_DEFAULT_STORAGE_SUPPLY_CODE`` env var to a Supply row via
the projection; any failure mode below causes the app to refuse to start
(fail-loud).

These are not domain errors raised by the decider; they are lifespan-tier
errors raised by ``bootstrap_default_storage_supply`` before any HTTP
route opens. Operator remediation is described in the per-kind message.

## One class, one kind enum

The four failure modes (env-var-unset-with-legacy-data, missing Supply,
wrong kind, non-Available status) all carry the same conceptual shape:
"lifespan failed to resolve the default storage Supply". Per the
altitude-correction in PR #60 code review, they collapse to a single
``DefaultStorageSupplyBootstrapError`` carrying a
``DefaultStorageSupplyBootstrapFailure`` enum discriminator plus
per-kind context fields, instead of four near-identical subclasses.
"""

from enum import StrEnum


class DefaultStorageSupplyBootstrapFailure(StrEnum):
    """Discriminator for the four lifespan-bootstrap failure modes."""

    CODE_UNSET = "CodeUnset"
    NOT_FOUND = "NotFound"
    KIND_MISMATCH = "KindMismatch"
    NOT_AVAILABLE = "NotAvailable"


class DefaultStorageSupplyBootstrapError(Exception):
    """Lifespan boot failed to resolve the default storage Supply.

    Carries a ``kind`` discriminator and per-kind context fields. Use
    the ``kind`` attribute (a :class:`DefaultStorageSupplyBootstrapFailure`
    member) to branch on the specific failure mode.

    Operator remediation depends on ``kind``:

      - ``CODE_UNSET``: set ``SELF_FACILITY_DEFAULT_STORAGE_SUPPLY_CODE`` in
        the app environment to the ``code`` of an existing storage-kind
        Available Supply, then restart.
      - ``NOT_FOUND``: register the Supply first via ``register_supply``
        REST/MCP, or fix the env var to point at an already-registered
        storage-kind Supply.
      - ``KIND_MISMATCH``: point the env var at a different Supply whose
        kind is ``"Storage"``, or register a new storage-kind Supply.
      - ``NOT_AVAILABLE``: mark the Supply Available via
        ``mark_supply_available`` (or operator equivalent), or point the
        env var at a different Available storage Supply.
    """

    def __init__(
        self,
        kind: DefaultStorageSupplyBootstrapFailure,
        *,
        message: str,
        supply_code: str | None = None,
        legacy_dataset_count: int | None = None,
        actual_kind: str | None = None,
        actual_status: str | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.supply_code = supply_code
        self.legacy_dataset_count = legacy_dataset_count
        self.actual_kind = actual_kind
        self.actual_status = actual_status
