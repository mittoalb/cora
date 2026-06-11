"""The `RemoveDatasetFromEdition` command."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RemoveDatasetFromEdition:
    """Remove an existing Dataset from a Registered Edition.

    Strict-not-idempotent: not-member raises
    `EditionDatasetNotMemberError`. Removing the last Dataset raises
    `EditionCannotBeEmptyError`.
    """

    edition_id: UUID
    dataset_id: UUID
