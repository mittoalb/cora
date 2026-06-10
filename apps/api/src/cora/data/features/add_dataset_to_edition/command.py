"""The `AddDatasetToEdition` command."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AddDatasetToEdition:
    """Add an existing Dataset to a Registered Edition.

    Strict-not-idempotent: re-add raises `EditionDatasetAlreadyMemberError`.
    """

    edition_id: UUID
    dataset_id: UUID
