"""The `ListDatasets` query: intent dataclass for keyset-paginated
list of datasets from the projection.

Three optional filters: status (Registered / Discarded),
producing_run_id (which Run produced this Dataset), subject_id
(which Subject this Dataset measured). Cursor encodes (created_at,
dataset_id).
"""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

DatasetStatusFilter = Literal["Registered", "Discarded"]


@dataclass(frozen=True)
class ListDatasets:
    """Read a keyset-paginated page of datasets from the projection."""

    cursor: str | None = None
    """Opaque base64 cursor from a previous page's `next_cursor`."""

    limit: int = 50
    """Page size cap. Default 50, max 100 (route enforces)."""

    status: DatasetStatusFilter | None = None
    """Optional status filter (Registered / Discarded)."""

    producing_run_id: UUID | None = None
    """Optional `producing_run_id` filter: returns Datasets produced
    by the given Run. Pass `None` (omit) for "any Run"."""

    subject_id: UUID | None = None
    """Optional `subject_id` filter: returns Datasets measuring the
    given Subject. Pass `None` (omit) for "any Subject"."""
