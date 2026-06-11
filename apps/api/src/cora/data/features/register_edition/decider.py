"""Pure decider for the `RegisterEdition` command.

## Firing order (per design memo)

  1. Pydantic 422 boundary parse-shape (off-decider).
  2. (handler) UnauthorizedError if Authorize denies.
  3. VO field validation: EditionTitle, SpdxIdentifier (if supplied),
     EditionKind closed-enum check.
  4. publication_year range check (if supplied).
  5. Creators tuple-level validation (non-empty + no dup + per-creator
     affiliation bound via Creator __post_init__).
  6. dataset_ids non-empty -> EmptyDatasetIdsAtRegistrationError.
  7. State-is-None genesis guard -> EditionAlreadyExistsError.
  8. (handler) Dataset pre-load -> DatasetNotFoundError per missing id.
  9. Per-Dataset Discarded guard -> EditionCannotBindToDiscardedDatasetError.
  10. Emit EditionRegistered (dataset_ids sorted in payload; creators
      preserve order).
"""

from datetime import datetime
from uuid import UUID

from cora.data.aggregates.dataset import DatasetStatus
from cora.data.aggregates.edition import (
    Creator,
    Edition,
    EditionAlreadyExistsError,
    EditionCannotBindToDiscardedDatasetError,
    EditionKind,
    EditionRegistered,
    EditionTitle,
    EmptyDatasetIdsAtRegistrationError,
    InvalidEditionKindError,
    SpdxIdentifier,
    validate_creators,
    validate_publication_year,
)
from cora.data.features.register_edition.command import RegisterEdition
from cora.data.features.register_edition.context import EditionRegistrationContext
from cora.shared.identity import ActorId


def decide(
    state: Edition | None,
    command: RegisterEdition,
    *,
    context: EditionRegistrationContext,
    now: datetime,
    new_id: UUID,
    registered_by: ActorId,
) -> list[EditionRegistered]:
    """Decide the events produced by registering a new Edition.

    Invariants:
      (Firing order per the docstring header.)
      - title must be valid -> InvalidEditionTitleError
      - kind must be in the closed EditionKind enum
        -> InvalidEditionKindError
      - license, if supplied, must be a valid SPDX identifier
        -> InvalidSpdxIdentifierError
      - publication_year, if supplied, must fall in [1900, current+5]
        -> InvalidPublicationYearError
      - creators tuple must be non-empty + free of duplicate actor_ids
        + every affiliation within bound -> InvalidCreatorsError
      - dataset_ids must be non-empty
        -> EmptyDatasetIdsAtRegistrationError
      - state must be None (genesis-only)
        -> EditionAlreadyExistsError
      - each member Dataset must not be Discarded
        -> EditionCannotBindToDiscardedDatasetError
    """
    # Step 3a: title VO.
    title = EditionTitle(command.title)

    # Step 3b: kind closed-enum check (defensive; Pydantic also enforces).
    try:
        kind = EditionKind(command.kind)
    except ValueError as exc:
        raise InvalidEditionKindError(command.kind) from exc

    # Step 3c: optional license VO.
    license_value: SpdxIdentifier | None = None
    if command.license is not None:
        license_value = SpdxIdentifier(command.license)

    # Step 4: optional publication year range check.
    publication_year: int | None = None
    if command.publication_year is not None:
        publication_year = validate_publication_year(
            command.publication_year, current_year=now.year
        )

    # Step 5: creators tuple. Construct typed Creators (each one runs
    # __post_init__ for affiliation bounds); then tuple-level invariants.
    creators_typed = tuple(
        Creator(actor_id=ActorId(entry.actor_id), affiliation=entry.affiliation)
        for entry in command.creators
    )
    validate_creators(creators_typed)

    # Step 6: dataset_ids non-empty.
    if not command.dataset_ids:
        raise EmptyDatasetIdsAtRegistrationError()

    # Step 7: genesis-only state guard.
    if state is not None:
        raise EditionAlreadyExistsError(state.id)

    # Step 9: per-Dataset Discarded guard (context is keyed by
    # dataset_id; the handler has already raised DatasetNotFoundError
    # upstream for any unresolved id).
    for dataset_id in command.dataset_ids:
        dataset = context.datasets[dataset_id]
        if dataset.status is DatasetStatus.DISCARDED:
            raise EditionCannotBindToDiscardedDatasetError(dataset_id=dataset_id)

    # Step 10: emit EditionRegistered.
    return [
        EditionRegistered(
            edition_id=new_id,
            kind=kind.value,
            title=title.value,
            dataset_ids=tuple(sorted(command.dataset_ids)),
            creators=tuple(
                {
                    "actor_id": creator.actor_id,
                    "affiliation": creator.affiliation,
                }
                for creator in creators_typed
            ),
            publisher_facility_code=command.publisher_facility_code,
            publication_year=publication_year,
            license=license_value.value if license_value is not None else None,
            occurred_at=now,
            registered_by=registered_by,
        )
    ]
