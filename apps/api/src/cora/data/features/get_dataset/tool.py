"""MCP tool for the `get_dataset` query slice.

Returns a structured `DatasetOutput` mirroring the REST `DatasetResponse`
shape (nested checksum + encoding, sorted set fields). MCP-side
404-equivalent uses the FastMCP `isError` mechanism via raised
exception → MCP result.
"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.data._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.data.aggregates.dataset import DATASET_NAME_MAX_LENGTH, DatasetNotFoundError
from cora.data.features.get_dataset.handler import Handler
from cora.data.features.get_dataset.query import GetDataset
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class ChecksumOutput(BaseModel):
    algorithm: str
    value: str


class EncodingOutput(BaseModel):
    media_type: str
    conforms_to: list[str]


class DatasetOutput(BaseModel):
    """Structured output of the `get_dataset` MCP tool."""

    id: UUID
    name: str = Field(..., max_length=DATASET_NAME_MAX_LENGTH)
    uri: str
    checksum: ChecksumOutput
    byte_size: int
    encoding: EncodingOutput
    producing_run_id: UUID | None
    subject_id: UUID | None
    derived_from: list[UUID]
    status: str


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_dataset` tool on the given MCP server."""

    @mcp.tool(
        name="get_dataset",
        description=(
            "Read the current state of an existing Dataset by id. Returns "
            "the full Dataset metadata (URI, checksum, byte_size, encoding, "
            "cross-aggregate refs, status). Raises if the dataset_id has "
            "no events in the store."
        ),
    )
    async def get_dataset_tool(  # pyright: ignore[reportUnusedFunction]
        dataset_id: Annotated[
            UUID,
            Field(description="Target dataset's id."),
        ],
    ) -> DatasetOutput:
        handler = get_handler()
        dataset = await handler(
            GetDataset(dataset_id=dataset_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        if dataset is None:
            raise DatasetNotFoundError(dataset_id)
        return DatasetOutput(
            id=dataset.id,
            name=dataset.name.value,
            uri=dataset.uri.value,
            checksum=ChecksumOutput(
                algorithm=dataset.checksum.algorithm,
                value=dataset.checksum.value,
            ),
            byte_size=dataset.byte_size,
            encoding=EncodingOutput(
                media_type=dataset.encoding.media_type,
                conforms_to=sorted(dataset.encoding.conforms_to),
            ),
            producing_run_id=dataset.producing_run_id,
            subject_id=dataset.subject_id,
            derived_from=sorted(dataset.derived_from, key=str),
            status=dataset.status.value,
        )
