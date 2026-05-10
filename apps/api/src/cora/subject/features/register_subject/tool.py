"""MCP tool for the `register_subject` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool. MCP tools currently bypass header extraction
(see CONTRIBUTING.md "Production hardening" section) and use
`SYSTEM_PRINCIPAL_ID` directly until the MCP auth-flow phase lands.
"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.observability import current_correlation_id
from cora.subject._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.subject.aggregates.subject import SUBJECT_NAME_MAX_LENGTH
from cora.subject.features.register_subject.command import RegisterSubject
from cora.subject.features.register_subject.handler import IdempotentHandler


class RegisterSubjectOutput(BaseModel):
    """Structured output of the `register_subject` MCP tool."""

    subject_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `register_subject` tool on the given MCP server."""

    @mcp.tool(
        name="register_subject",
        description="Register a new subject with the given display name.",
    )
    async def register_subject_tool(  # pyright: ignore[reportUnusedFunction]
        name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=SUBJECT_NAME_MAX_LENGTH,
                description="Display name for the new subject.",
            ),
        ],
    ) -> RegisterSubjectOutput:
        handler = get_handler()
        subject_id = await handler(
            RegisterSubject(name=name),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        return RegisterSubjectOutput(subject_id=subject_id)
