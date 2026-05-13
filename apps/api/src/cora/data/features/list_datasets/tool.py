"""MCP tool for the `list_datasets` query slice."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.data._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.data.aggregates.dataset import (
    DATASET_NAME_MAX_LENGTH,
    DATASET_URI_MAX_LENGTH,
)
from cora.data.features.list_datasets.handler import Handler
from cora.data.features.list_datasets.query import DatasetStatusFilter, ListDatasets
from cora.infrastructure.observability import current_correlation_id


class DatasetSummaryRow(BaseModel):
    dataset_id: UUID
    name: str = Field(..., max_length=DATASET_NAME_MAX_LENGTH)
    uri: str = Field(..., max_length=DATASET_URI_MAX_LENGTH)
    producing_run_id: UUID | None
    subject_id: UUID | None
    status: DatasetStatusFilter
    created_at: datetime


class DatasetListOutput(BaseModel):
    """Structured output of the `list_datasets` MCP tool."""

    items: list[DatasetSummaryRow]
    next_cursor: str | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `list_datasets` tool on the given MCP server."""

    @mcp.tool(
        name="list_datasets",
        description=(
            "Cursor-paginated list of datasets. Optional `status` "
            "filter accepts: Registered, Discarded. Optional "
            "`producing_run_id` and `subject_id` filters narrow to "
            "Datasets produced by one Run / measuring one Subject. "
            "Pass `cursor` from a previous page's `next_cursor`."
        ),
    )
    async def list_datasets_tool(  # pyright: ignore[reportUnusedFunction]
        cursor: Annotated[
            str | None,
            Field(description="Opaque cursor from a previous response."),
        ] = None,
        limit: Annotated[
            int,
            Field(ge=1, le=100, description="Page size cap (max 100)."),
        ] = 50,
        status: Annotated[
            DatasetStatusFilter | None,
            Field(description="Optional status filter; omit to list all."),
        ] = None,
        producing_run_id: Annotated[
            UUID | None,
            Field(description="Optional Run-id filter."),
        ] = None,
        subject_id: Annotated[
            UUID | None,
            Field(description="Optional Subject-id filter."),
        ] = None,
    ) -> DatasetListOutput:
        handler = get_handler()
        page = await handler(
            ListDatasets(
                cursor=cursor,
                limit=limit,
                status=status,
                producing_run_id=producing_run_id,
                subject_id=subject_id,
            ),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        return DatasetListOutput(
            items=[
                DatasetSummaryRow(
                    dataset_id=item.dataset_id,
                    name=item.name,
                    uri=item.uri,
                    producing_run_id=item.producing_run_id,
                    subject_id=item.subject_id,
                    status=item.status,  # type: ignore[arg-type]
                    created_at=item.created_at,
                )
                for item in page.items
            ],
            next_cursor=page.next_cursor,
        )
