"""BC-application-layer errors for the Equipment BC.

These errors are raised by application handlers (not domain logic)
and mapped to HTTP / MCP responses by the BC's exception handlers in
`cora/equipment/routes.py`.

Domain errors (raised by aggregates / deciders) ordinarily live with
their aggregate, for example `aggregates/family/state.py`. The
exception is errors raised by VOs that live at the BC root (shared
across aggregates): those domain errors live here too, since the
architecture fitness (`test_no_domain_errors_outside_aggregate_or_errors_module`)
only exempts aggregate state modules and this file. The Placement
and Drawing VOs in `_placement.py` / `_drawing.py` are the first
instance; their `InvalidPlacementError` /
`InvalidDrawingNumberError` / `InvalidDrawingRevisionError` raise
sites stay in the VO `__post_init__`, but the class definitions
live here.

Distinct class from `cora.access.errors.UnauthorizedError` /
`cora.subject.errors.UnauthorizedError` / `cora.trust.errors.UnauthorizedError`:
each BC owns its own application-error namespace so an Equipment
403 is distinguishable from other BCs' 403s in logs / aggregator
filters (documented in CONTRIBUTING.md "BC-application-layer errors").
Cross-BC consumers catching authorization failures import per-BC.
"""


class UnauthorizedError(Exception):
    """The Authorize port denied the command."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class InvalidPlacementError(ValueError):
    """A Placement failed VO-level domain validation.

    Failure modes at the VO layer:
      - Any tolerance is negative (tolerances are bilateral; zero
        means "exact", negative is meaningless).

    Cross-aggregate validations (parent_frame must reference an
    active Frame, etc.) happen at the handler / decider layer, not
    in the VO. Per the design memo: the VO is closed-shape; the
    handler is where cross-aggregate preconditions land.

    `reason` names the offending axis for diagnostics; the route
    layer's `_handle_validation_error` reads `str(exc)` (which
    formats as "Invalid Placement: <reason>"), so the reason is
    embedded in the message that surfaces in the 400 body.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid Placement: {reason}")
        self.reason = reason


class InvalidDrawingError(ValueError):
    """Base class for Drawing VO validation failures.

    Tests catch the specific subclasses (`InvalidDrawingNumberError`,
    `InvalidDrawingRevisionError`) when they need to distinguish the
    failing field. The route layer's `_handle_validation_error`
    catches the base class and surfaces `str(exc)` into the 400 body,
    so the formatted message is the user-facing surface; subclass-
    specific routing is not required today.
    """


class InvalidDrawingNumberError(InvalidDrawingError):
    """`Drawing.number` failed bounded-text validation.

    Raised by `validate_bounded_text` when the trimmed number is
    empty / whitespace-only or exceeds the cap (the cap constant
    `DRAWING_NUMBER_MAX_LENGTH` lives with the VO in `_drawing.py`).
    `value` carries the original untrimmed input for diagnostics
    (mirrors the `InvalidAssetPortNameError` shape).
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Invalid Drawing number (must be 1-200 chars after trimming, got: {value!r})"
        )
        self.value = value


class InvalidDrawingRevisionError(InvalidDrawingError):
    """`Drawing.revision` failed bounded-text validation.

    Raised by `validate_bounded_text` when the revision is present
    but trimmed empty or exceeds the cap (the cap constant
    `DRAWING_REVISION_MAX_LENGTH` lives with the VO in
    `_drawing.py`). To indicate 'latest' (resolves at the adapter),
    pass `revision=None` instead of an empty string. `value` carries
    the original untrimmed input.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Invalid Drawing revision (must be 1-100 chars after trimming, "
            f"or None for 'latest'; got: {value!r})"
        )
        self.value = value
