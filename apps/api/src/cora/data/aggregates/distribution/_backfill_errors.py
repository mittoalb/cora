"""Lifespan-bootstrap error classes for the Slice 2 Distribution backfill.

Per [[project-data-distribution-design]] L23 + L23a: the Slice 2 backfill
runs as a runtime-Python lifespan step at app startup (NOT an Atlas SQL
migration, because Atlas CLI is a separate process and cannot read
session-local GUCs set by app lifespan). The bootstrap resolves the
``SELF_FACILITY_DEFAULT_STORAGE_SUPPLY_CODE`` env var to a Supply row via
the projection; any of the four failure modes below cause the app to
refuse to start (fail-loud).

These are not domain errors raised by the decider; they are lifespan-tier
errors raised by ``bootstrap_default_storage_supply`` before any HTTP
route opens. Operator remediation is described in the per-class message.
"""


class DefaultStorageSupplyCodeUnsetError(Exception):
    """Raised at lifespan when ``SELF_FACILITY_DEFAULT_STORAGE_SUPPLY_CODE`` is unset.

    Only raised when legacy ``Dataset`` rows exist (the backfill has work
    to do); a clean install with no Datasets succeeds with the env var
    unset (no-op).

    Operator remediation: set ``SELF_FACILITY_DEFAULT_STORAGE_SUPPLY_CODE``
    in the app environment to the ``code`` of an existing storage-kind
    Available Supply, then restart.
    """

    def __init__(self, legacy_dataset_count: int) -> None:
        super().__init__(
            f"Cannot bootstrap default storage Supply: "
            f"SELF_FACILITY_DEFAULT_STORAGE_SUPPLY_CODE env var is unset "
            f"but {legacy_dataset_count} legacy Dataset row(s) exist that "
            f"need backfill. Set the env var to an existing storage-kind "
            f"Available Supply code, then restart."
        )
        self.legacy_dataset_count = legacy_dataset_count


class DefaultStorageSupplyNotFoundError(Exception):
    """Raised at lifespan when the env-var Supply code does not resolve.

    The env var is set but ``proj_supply_summary`` has no row with the
    matching code. Operator remediation: register the Supply first via
    ``register_supply`` REST/MCP, OR fix the env var to point at an
    already-registered storage-kind Supply.
    """

    def __init__(self, supply_code: str) -> None:
        super().__init__(
            f"Cannot bootstrap default storage Supply: "
            f"SELF_FACILITY_DEFAULT_STORAGE_SUPPLY_CODE={supply_code!r} "
            f"does not resolve in proj_supply_summary. Register the Supply "
            f"first or fix the env var, then restart."
        )
        self.supply_code = supply_code


class DefaultStorageSupplyKindMismatchError(Exception):
    """Raised at lifespan when the resolved Supply has ``kind != "Storage"``.

    The env-var Supply exists but is not a storage-kind Supply
    (per [[project-data-distribution-design]] L30 + the Supply BC's
    closed-StrEnum kind values, currently free-form bare-str). Operator
    remediation: point the env var at a different Supply whose kind is
    ``"Storage"``, or register a new storage-kind Supply.
    """

    def __init__(self, supply_code: str, actual_kind: str) -> None:
        super().__init__(
            f"Cannot bootstrap default storage Supply: "
            f"SELF_FACILITY_DEFAULT_STORAGE_SUPPLY_CODE={supply_code!r} "
            f"resolved to a Supply with kind={actual_kind!r} (expected "
            f"'Storage'). Point env var at a storage-kind Supply, restart."
        )
        self.supply_code = supply_code
        self.actual_kind = actual_kind


class DefaultStorageSupplyNotAvailableError(Exception):
    """Raised at lifespan when the resolved Supply has ``status != "Available"``.

    The env-var Supply exists and is storage-kind, but its lifecycle
    status is Degraded / Unavailable / Recovering / Decommissioned.
    Operator remediation: mark the Supply Available via
    ``mark_supply_available`` (or operator equivalent), OR point the
    env var at a different Available storage Supply.
    """

    def __init__(self, supply_code: str, actual_status: str) -> None:
        super().__init__(
            f"Cannot bootstrap default storage Supply: "
            f"SELF_FACILITY_DEFAULT_STORAGE_SUPPLY_CODE={supply_code!r} "
            f"resolved to a Supply with status={actual_status!r} "
            f"(expected 'Available'). Mark the Supply available or point "
            f"env var at a different Available Supply, restart."
        )
        self.supply_code = supply_code
        self.actual_status = actual_status
