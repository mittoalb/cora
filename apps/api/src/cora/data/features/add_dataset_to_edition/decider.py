"""Pure decider for the `AddDatasetToEdition` command.

Firing order:
  1. (handler) UnauthorizedError if denied.
  2. (handler) load Edition + Dataset.
  3. state must be non-None -> EditionNotFoundError.
  4. state.status must be REGISTERED -> EditionNotInRegisteredStateError.
  5. context.dataset.status must not be DISCARDED
     -> EditionCannotBindToDiscardedDatasetError.
  6. dataset_id must not already be in state.dataset_ids
     -> EditionDatasetAlreadyMemberError.
  7. Emit EditionDatasetAdded.
"""

from datetime import datetime

from cora.data.aggregates.dataset import DatasetStatus
from cora.data.aggregates.edition import (
    Edition,
    EditionCannotBindToDiscardedDatasetError,
    EditionDatasetAdded,
    EditionDatasetAlreadyMemberError,
    EditionNotFoundError,
    EditionNotInRegisteredStateError,
    EditionStatus,
)
from cora.data.features.add_dataset_to_edition.command import AddDatasetToEdition
from cora.data.features.add_dataset_to_edition.context import (
    AddDatasetToEditionContext,
)
from cora.shared.identity import ActorId


def decide(
    state: Edition | None,
    command: AddDatasetToEdition,
    *,
    context: AddDatasetToEditionContext,
    now: datetime,
    added_by: ActorId,
) -> list[EditionDatasetAdded]:
    """Decide the events produced by adding a Dataset to an Edition.

    Invariants:
      (Firing order per the docstring header.)
      - state must be non-None -> EditionNotFoundError
      - state.status must be REGISTERED
        -> EditionNotInRegisteredStateError
      - context.dataset.status must not be DISCARDED
        -> EditionCannotBindToDiscardedDatasetError
      - dataset_id must not already be a member
        -> EditionDatasetAlreadyMemberError
    """
    if state is None:
        raise EditionNotFoundError(command.edition_id)
    if state.status is not EditionStatus.REGISTERED:
        raise EditionNotInRegisteredStateError(edition_id=state.id, current_status=state.status)
    if context.dataset.status is DatasetStatus.DISCARDED:
        raise EditionCannotBindToDiscardedDatasetError(dataset_id=command.dataset_id)
    if command.dataset_id in state.dataset_ids:
        raise EditionDatasetAlreadyMemberError(edition_id=state.id, dataset_id=command.dataset_id)
    return [
        EditionDatasetAdded(
            edition_id=state.id,
            dataset_id=command.dataset_id,
            occurred_at=now,
            added_by=added_by,
        )
    ]
