"""Application handler for the ``record_attestation`` slice.

Genesis-style create handler. Pre-loads two cross-aggregate refs:

  1. The parent Dataset (always; ``load_dataset(command.dataset_id)``).
  2. The bound Distribution (only when ``command.distribution_id`` is
     not None; ``load_distribution(command.distribution_id)``).

Both pre-loads happen BEFORE invoking the pure decider per L15 + L17.
The ``AttestationKindNotYetSupportedError`` rejection runs at the
handler tier (before any event-store reads) so unsupported kinds do
not leak information about Dataset / Distribution existence.

## No ``load_attestation(new_id)``

``new_id`` is a freshly-allocated UUIDv7 from the IdGenerator port, so
the Attestation stream is guaranteed empty; the decider is invoked
with ``state=None`` and the same-stream-id race at append time is
caught by Postgres ``ConcurrencyError``.
"""

from typing import Protocol
from uuid import UUID

from cora.data.aggregates.attestation import (
    AttestationDistributionNotFoundError,
    AttestationKind,
    AttestationKindNotYetSupportedError,
    event_type_name,
    to_payload,
)
from cora.data.aggregates.dataset import (
    DatasetNotFoundError,
    load_dataset,
)
from cora.data.aggregates.distribution import load_distribution
from cora.data.errors import UnauthorizedError
from cora.data.features.record_attestation.command import RecordAttestation
from cora.data.features.record_attestation.context import (
    AttestationRecordingContext,
)
from cora.data.features.record_attestation.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.identity import ActorId

_STREAM_TYPE = "Attestation"
_COMMAND_NAME = "RecordAttestation"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare record_attestation handler, what ``bind()`` returns."""

    async def __call__(
        self,
        command: RecordAttestation,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """record_attestation handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: RecordAttestation,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(deps: Kernel) -> Handler:
    """Build a record_attestation handler closed over the shared deps."""

    async def handler(
        command: RecordAttestation,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        _log.info(
            "record_attestation.start",
            command_name=_COMMAND_NAME,
            dataset_id=str(command.dataset_id),
            distribution_id=(
                str(command.distribution_id) if command.distribution_id is not None else None
            ),
            kind=command.kind,
            outcome=command.outcome,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "record_attestation.denied",
                command_name=_COMMAND_NAME,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        # Handler-tier kind-not-yet-supported guard. Runs BEFORE any
        # event-store reads to avoid leaking information about Dataset
        # / Distribution existence to callers of unsupported kinds.
        # The decider re-checks this defensively for the in-process
        # bypass case.
        if command.kind != AttestationKind.CHECKSUM_VERIFIED.value:
            try:
                _ = AttestationKind(command.kind)
            except ValueError:
                # Invalid value lands at the decider's InvalidAttestationKindError.
                pass
            else:
                raise AttestationKindNotYetSupportedError(command.kind)

        # Pre-load parent Dataset (same-BC, always required).
        dataset = await load_dataset(deps.event_store, command.dataset_id)
        if dataset is None:
            raise DatasetNotFoundError(command.dataset_id)

        # Pre-load Distribution (only when distribution_id is set).
        distribution = None
        if command.distribution_id is not None:
            distribution = await load_distribution(deps.event_store, command.distribution_id)
            if distribution is None:
                raise AttestationDistributionNotFoundError(command.distribution_id)

        context = AttestationRecordingContext(dataset=dataset, distribution=distribution)

        new_id = deps.id_generator.new_id()
        now = deps.clock.now()

        domain_events = decide(
            state=None,
            command=command,
            context=context,
            now=now,
            new_id=new_id,
            attested_by=ActorId(principal_id),
        )

        new_events = [
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=event.occurred_at,
                event_id=deps.id_generator.new_id(),
                command_name=_COMMAND_NAME,
                correlation_id=correlation_id,
                causation_id=causation_id,
                principal_id=principal_id,
            )
            for event in domain_events
        ]
        await deps.event_store.append(
            stream_type=_STREAM_TYPE,
            stream_id=new_id,
            expected_version=0,
            events=new_events,
        )

        _log.info(
            "record_attestation.success",
            command_name=_COMMAND_NAME,
            attestation_id=str(new_id),
            dataset_id=str(command.dataset_id),
            distribution_id=(
                str(command.distribution_id) if command.distribution_id is not None else None
            ),
            kind=command.kind,
            outcome=command.outcome,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            event_count=len(new_events),
        )
        return new_id

    return handler
