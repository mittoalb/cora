"""The `CompleteProcedure` command -- intent dataclass for this slice.

Single-source happy-path terminal: `Running -> Completed`. Slim
command (id only); no reason field. Mirrors `CompleteRun`.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CompleteProcedure:
    """Mark an existing Procedure as completed (happy-path terminal)."""

    procedure_id: UUID
