"""Pure decider for the `RemoveDatasetFromEdition` command.

Firing order:
  1. (handler) UnauthorizedError if denied.
  2. (handler) load Edition; no Dataset peer load (set-removal is
     well-defined without it).
  3. state must be non-None -> EditionNotFoundError.
  4. state.status must be REGISTERED -> EditionNotInRegisteredStateError.
  5. dataset_id must be in state.dataset_ids
     -> EditionDatasetNotMemberError.
  6. Post-removal set must be non-empty -> EditionCannotBeEmptyError.
  7. Emit EditionDatasetRemoved.
"""

from datetime import datetime

from cora.data.aggregates.edition import (
    Edition,
    EditionCannotBeEmptyError,
    EditionDatasetNotMemberError,
    EditionDatasetRemoved,
    EditionNotFoundError,
    EditionNotInRegisteredStateError,
    EditionStatus,
)
from cora.data.features.remove_dataset_from_edition.command import (
    RemoveDatasetFromEdition,
)
from cora.shared.identity import ActorId


def decide(
    state: Edition | None,
    command: RemoveDatasetFromEdition,
    *,
    now: datetime,
    removed_by: ActorId,
) -> list[EditionDatasetRemoved]:
    """Decide the events produced by removing a Dataset from an Edition.

    Invariants:
      (Firing order per the docstring header.)
      - state must be non-None -> EditionNotFoundError
      - state.status must be REGISTERED
        -> EditionNotInRegisteredStateError
      - dataset_id must be a current member
        -> EditionDatasetNotMemberError
      - removing the last member is forbidden
        -> EditionCannotBeEmptyError
    """
    if state is None:
        raise EditionNotFoundError(command.edition_id)
    if state.status is not EditionStatus.REGISTERED:
        raise EditionNotInRegisteredStateError(edition_id=state.id, current_status=state.status)
    if command.dataset_id not in state.dataset_ids:
        raise EditionDatasetNotMemberError(edition_id=state.id, dataset_id=command.dataset_id)
    # Post-removal cardinality check.
    if len(state.dataset_ids) == 1:
        raise EditionCannotBeEmptyError(edition_id=state.id)
    return [
        EditionDatasetRemoved(
            edition_id=state.id,
            dataset_id=command.dataset_id,
            occurred_at=now,
            removed_by=removed_by,
        )
    ]
