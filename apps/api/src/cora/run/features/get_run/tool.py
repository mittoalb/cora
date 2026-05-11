"""MCP tool for the `get_run` query slice."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.observability import current_correlation_id
from cora.run._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.run.aggregates.run import RUN_NAME_MAX_LENGTH
from cora.run.features.get_run.handler import Handler
from cora.run.features.get_run.query import GetRun


class RunOutput(BaseModel):
    """Structured output of the `get_run` MCP tool."""

    id: UUID
    name: str = Field(..., max_length=RUN_NAME_MAX_LENGTH)
    plan_id: UUID
    subject_id: UUID | None
    status: str


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `get_run` tool on the given MCP server."""

    @mcp.tool(
        name="get_run",
        description="Read the current state of an existing run by id.",
    )
    async def get_run_tool(  # pyright: ignore[reportUnusedFunction]
        run_id: Annotated[
            UUID,
            Field(description="Target run's id."),
        ],
    ) -> RunOutput:
        handler = get_handler()
        run = await handler(
            GetRun(run_id=run_id),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        if run is None:
            msg = f"Run {run_id} not found"
            raise ValueError(msg)
        return RunOutput(
            id=run.id,
            name=run.name.value,
            plan_id=run.plan_id,
            subject_id=run.subject_id,
            status=run.status.value,
        )
