"""Seal aggregate: per-facility singleton that signs the head pointer.

Public surface: status enum + aggregate root + 9 error classes + 5
events + evolver + load helpers + lifecycle-timestamps view +
key-separation guard. Pattern matches
`cora.calibration.aggregates.calibration.__init__` and
`cora.safety.aggregates.clearance.__init__`. The aggregate's
deciders, projections, slices, routes, MCP tools, and wire module
live alongside this module.
"""

from cora.federation.aggregates.seal._key_separation import verify_key_separation
from cora.federation.aggregates.seal.events import (
    SealEvent,
    SealInitialized,
    SealOnlineKeyRotated,
    SealPointerSigned,
    SealRepublishingCompleted,
    SealRepublishingStarted,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.federation.aggregates.seal.evolver import evolve, fold
from cora.federation.aggregates.seal.read import (
    SealLifecycleTimestamps,
    load_seal,
    load_seal_timestamps,
)
from cora.federation.aggregates.seal.state import (
    InvalidSealFacilityIdError,
    InvalidSealHeadHashError,
    Seal,
    SealAlreadyExistsError,
    SealCannotCompleteRepublishingError,
    SealCannotInitializeWithInactiveCredentialError,
    SealCannotRotateError,
    SealCannotRotateWithInactiveCredentialError,
    SealCannotSignError,
    SealCannotStartRepublishingError,
    SealKeyCollisionError,
    SealKeyPurposeMismatchError,
    SealNotFoundError,
    SealSequenceNumberRegressionError,
    SealStatus,
)

__all__ = [
    "InvalidSealFacilityIdError",
    "InvalidSealHeadHashError",
    "Seal",
    "SealAlreadyExistsError",
    "SealCannotCompleteRepublishingError",
    "SealCannotInitializeWithInactiveCredentialError",
    "SealCannotRotateError",
    "SealCannotRotateWithInactiveCredentialError",
    "SealCannotSignError",
    "SealCannotStartRepublishingError",
    "SealEvent",
    "SealInitialized",
    "SealKeyCollisionError",
    "SealKeyPurposeMismatchError",
    "SealLifecycleTimestamps",
    "SealNotFoundError",
    "SealOnlineKeyRotated",
    "SealPointerSigned",
    "SealRepublishingCompleted",
    "SealRepublishingStarted",
    "SealSequenceNumberRegressionError",
    "SealStatus",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_seal",
    "load_seal_timestamps",
    "to_payload",
    "verify_key_separation",
]
