"""Re-exports for the Credential aggregate.

Pattern matches `cora.calibration.aggregates.calibration.__init__`:
events, state, evolver, and read helpers are all surfaced at the
aggregate namespace so slices import `from
cora.federation.aggregates.credential import ...` without reaching
into individual modules.
"""

from cora.federation.aggregates.credential.events import (
    CredentialEvent,
    CredentialRegistered,
    CredentialRevoked,
    CredentialRotationAborted,
    CredentialRotationCompleted,
    CredentialRotationStarted,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.federation.aggregates.credential.evolver import evolve, fold
from cora.federation.aggregates.credential.read import (
    CredentialLifecycleTimestamps,
    load_credential,
    load_credential_timestamps,
)
from cora.federation.aggregates.credential.state import (
    Credential,
    CredentialAlreadyExistsError,
    CredentialCannotRevokeError,
    CredentialCannotRotateError,
    CredentialExpiredError,
    CredentialNotFoundError,
    CredentialPurpose,
    CredentialStatus,
    InvalidCredentialSecretRefError,
)

__all__ = [
    "Credential",
    "CredentialAlreadyExistsError",
    "CredentialCannotRevokeError",
    "CredentialCannotRotateError",
    "CredentialEvent",
    "CredentialExpiredError",
    "CredentialLifecycleTimestamps",
    "CredentialNotFoundError",
    "CredentialPurpose",
    "CredentialRegistered",
    "CredentialRevoked",
    "CredentialRotationAborted",
    "CredentialRotationCompleted",
    "CredentialRotationStarted",
    "CredentialStatus",
    "InvalidCredentialSecretRefError",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_credential",
    "load_credential_timestamps",
    "to_payload",
]
