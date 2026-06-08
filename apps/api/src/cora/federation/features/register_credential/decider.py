"""Pure decider for the `RegisterCredential` command.

Pure function: given the (always None) Credential state and a
`RegisterCredential` command, returns the events to append on the
Credential stream. No I/O, no awaits, no side effects.

`now`, `new_id`, and `registered_by` are injected by the
application handler from the Clock / IdGenerator ports and the
request envelope (the non-determinism principle: capture, don't
recompute).

The cross-BC `DecisionRegistered` audit event on the Decision
stream is built directly by the handler (not by this decider) and
written atomically alongside the `CredentialRegistered` event via
`EventStore.append_streams`. Decider stays focused on the Credential
BC's domain invariants.

Invariants:
  - State must be None (genesis-only)
    -> CredentialAlreadyExistsError
  - facility_code non-empty after trim AND a well-formed FacilityCode
    -> InvalidCredentialSecretRefError (re-used for field-shape
       violations across the aggregate per the shipped error class set)
  - audience non-empty after trim
    -> InvalidCredentialSecretRefError
  - secret_ref non-empty after trim
    -> InvalidCredentialSecretRefError
  - When expires_at is provided it must lie strictly after now
    -> CredentialExpiredError

`purpose` is a closed `CredentialPurpose` StrEnum, validated at the
Pydantic boundary (route / tool); the decider trusts the enum.
"""

from datetime import datetime
from uuid import UUID

from cora.federation.aggregates.credential import (
    Credential,
    CredentialAlreadyExistsError,
    CredentialExpiredError,
    CredentialRegistered,
    InvalidCredentialSecretRefError,
)
from cora.federation.features.register_credential.command import RegisterCredential
from cora.shared.facility_code import FacilityCode, InvalidFacilityCodeError
from cora.shared.identity import ActorId


def decide(
    state: Credential | None,
    command: RegisterCredential,
    *,
    now: datetime,
    new_id: UUID,
    registered_by: ActorId,
) -> list[CredentialRegistered]:
    """Decide the events produced by registering a new Credential.

    Invariants:
      - State must be None (genesis-only) -> CredentialAlreadyExistsError
      - facility_code non-empty after trim AND well-formed FacilityCode
        -> InvalidCredentialSecretRefError
      - audience non-empty after trim -> InvalidCredentialSecretRefError
      - secret_ref non-empty after trim -> InvalidCredentialSecretRefError
      - When set, expires_at must lie strictly after now
        -> CredentialExpiredError
    """
    if state is not None:
        raise CredentialAlreadyExistsError(state.id)

    canonical_facility = command.facility_code.strip()
    if not canonical_facility:
        raise InvalidCredentialSecretRefError("facility_code", command.facility_code)
    try:
        facility_code = FacilityCode(canonical_facility)
    except InvalidFacilityCodeError as exc:
        # Codepoint / length rejections inside the typed VO surface as
        # the slice's domain error class so the route mapping (HTTP 400)
        # stays unchanged from the pre-rename behaviour where the decider
        # only enforced non-empty after trim.
        raise InvalidCredentialSecretRefError("facility_code", command.facility_code) from exc

    audience = command.audience.strip()
    if not audience:
        raise InvalidCredentialSecretRefError("audience", command.audience)

    secret_ref = command.secret_ref.strip()
    if not secret_ref:
        raise InvalidCredentialSecretRefError("secret_ref", command.secret_ref)

    if command.expires_at is not None and command.expires_at <= now:
        raise CredentialExpiredError(new_id, command.expires_at)

    return [
        CredentialRegistered(
            credential_id=new_id,
            facility_code=facility_code,
            audience=audience,
            purpose=command.purpose,
            secret_ref=secret_ref,
            public_material_ref=command.public_material_ref,
            expires_at=command.expires_at,
            registered_by=registered_by,
            occurred_at=now,
        )
    ]


__all__ = ["decide"]
