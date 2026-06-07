"""BC-application-layer errors for the Equipment BC.

These errors are raised by application handlers (not domain logic)
and mapped to HTTP / MCP responses by the BC's exception handlers in
`cora/equipment/routes.py`.

Domain errors (raised by aggregates / deciders) live with their
aggregate, for example `aggregates/family/state.py`. Cross-aggregate
shared VOs (Placement, Drawing) live under `aggregates/_*.py` and
keep their error classes co-located in the same module: the tach
layering rule forbids `cora.equipment.aggregates` from depending
on `cora.equipment`, so VO-side error definitions cannot live here
in the BC root.

Distinct class from `cora.access.errors.UnauthorizedError` /
`cora.subject.errors.UnauthorizedError` / `cora.trust.errors.UnauthorizedError`:
each BC owns its own application-error namespace so an Equipment
403 is distinguishable from other BCs' 403s in logs / aggregator
filters (documented in CONTRIBUTING.md "BC-application-layer errors").
Cross-BC consumers catching authorization failures import per-BC.
"""

from uuid import UUID


class UnauthorizedError(Exception):
    """The Authorize port denied the command."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class PidinstSerializationError(Exception):
    """Base class for every PIDINST serializer precondition violation.

    Five concrete classes derive from this base: four pre-construction
    errors raised by `to_pidinst_record` before `PidinstRecord`
    construction (`AssetNameMissingError`, `LandingPageMissingError`,
    `OwnerStateNotAvailableError`, `ManufacturerStateNotAvailableError`)
    and one construction-time invariant error
    (`PidinstRecordInvariantError`) raised from
    `PidinstRecord.__post_init__`. Callers `except` once on this base
    to handle all five.
    """


class PidinstRecordInvariantError(PidinstSerializationError):
    """The PIDINST intermediate's `__post_init__` tripped a structural invariant.

    Distinct from the four typed pre-construction errors below: those
    describe missing source data on the input view; this describes a
    malformed intermediate that slipped past the pre-construction
    checks. Both share the `PidinstSerializationError` base so callers
    can `except` once.

    Raised explicitly via if-raise inside `PidinstRecord.__post_init__`
    for each of the nine invariants in section 6.7 of the design memo.
    Bare `assert` is intentionally avoided: it is stripped under
    `python -O` and would surface construction-time failures as an
    undocumented `AssertionError` distinct from the five named classes.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"PidinstRecord invariant violated: {reason}")
        self.reason = reason


class OwnerStateNotAvailableError(PidinstSerializationError):
    """The view carries no owner state; mandatory PIDINST property 5 cannot be emitted."""

    def __init__(self, asset_id: UUID) -> None:
        super().__init__(f"PIDINST mandatory property missing: owner for asset {asset_id}")
        self.asset_id = asset_id


class ManufacturerStateNotAvailableError(PidinstSerializationError):
    """The view has no Model binding; mandatory PIDINST property 6 cannot be emitted."""

    def __init__(self, asset_id: UUID) -> None:
        super().__init__(
            f"PIDINST mandatory property missing: manufacturer for asset {asset_id} "
            f"(no Model bound)"
        )
        self.asset_id = asset_id


class LandingPageMissingError(PidinstSerializationError):
    """`view.landing_page_url` is empty or whitespace-only."""

    def __init__(self, asset_id: UUID) -> None:
        super().__init__(f"PIDINST mandatory property missing: landingPage for asset {asset_id}")
        self.asset_id = asset_id


class AssetNameMissingError(PidinstSerializationError):
    """`view.asset_name` is empty or whitespace-only."""

    def __init__(self, asset_id: UUID) -> None:
        super().__init__(f"PIDINST mandatory property missing: name for asset {asset_id}")
        self.asset_id = asset_id


class VirtualAxisNotPidinstableError(Exception):
    """The target Asset is a virtual axis (carries a non-None `partition_rule`)
    and is structurally ineligible for PIDINST minting.

    PIDINST v1.0 requires a Manufacturer (Property 6) and at least one
    Owner (Property 5); virtual axes are software routing constructs
    that carry no vendor and no institutional steward. The Asset's
    partition_rule is the substrate that distinguishes the virtual case
    from a physical instrument.

    Raised at the PIDINST view-assembler tier before the serializer
    runs, so the route can map this to 404 (resource not applicable)
    rather than 409 (which would mis-signal "fix this by adding a
    Manufacturer"). Sits OUTSIDE the `PidinstSerializationError`
    hierarchy because the 409-mapped serializer errors all describe
    fixable view-state gaps; this one is structural and never fixable
    for the resource. See [[project_virtual_axis_aggregate_followup]].
    """

    def __init__(self, asset_id: UUID) -> None:
        super().__init__(
            f"Asset {asset_id} is a virtual axis (carries a partition_rule) and is "
            f"structurally not PIDINST-eligible; PIDINST v1.0 requires a Manufacturer "
            f"and Owner that virtual axes do not have"
        )
        self.asset_id = asset_id


class FixturePidinstSerializationError(PidinstSerializationError):
    """Base for every Fixture-tier PIDINST serializer precondition violation.

    Inherits from the cross-tier `PidinstSerializationError` so generic
    exception handlers that catch the base continue to function for
    both Asset-tier and Fixture-tier failures. Concrete Fixture-tier
    subclasses carry `fixture_id` (not `asset_id`); raising an
    Asset-tier sibling against a Fixture would be a semantic lie.
    """


class FixtureOwnerStateNotAvailableError(FixturePidinstSerializationError):
    """No bound Asset carries any owners; the Fixture's owners-union is empty."""

    def __init__(self, fixture_id: UUID) -> None:
        super().__init__(
            f"PIDINST mandatory property missing: owner for fixture {fixture_id} "
            f"(no bound Asset carries any owners)"
        )
        self.fixture_id = fixture_id


class FixtureManufacturerStateNotAvailableError(FixturePidinstSerializationError):
    """No bound Asset's Model carries any manufacturer; the union is empty."""

    def __init__(self, fixture_id: UUID) -> None:
        super().__init__(
            f"PIDINST mandatory property missing: manufacturer for fixture {fixture_id} "
            f"(no bound Asset carries any manufacturer)"
        )
        self.fixture_id = fixture_id


class FixtureLandingPageMissingError(FixturePidinstSerializationError):
    """`view.landing_page_url` is empty or whitespace-only."""

    def __init__(self, fixture_id: UUID) -> None:
        super().__init__(
            f"PIDINST mandatory property missing: landingPage for fixture {fixture_id}"
        )
        self.fixture_id = fixture_id


class FixtureNameMissingError(FixturePidinstSerializationError):
    """`view.name` is empty or whitespace-only."""

    def __init__(self, fixture_id: UUID) -> None:
        super().__init__(f"PIDINST mandatory property missing: name for fixture {fixture_id}")
        self.fixture_id = fixture_id
