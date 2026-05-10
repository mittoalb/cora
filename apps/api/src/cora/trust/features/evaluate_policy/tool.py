"""MCP tool for the `evaluate_policy` query slice.

Same handler the REST route uses, surfaced as an MCP tool. Returns
structured `EvaluatePolicyOutput` on hit (Allow or Deny). On miss
(policy doesn't exist) raises `ValueError` — FastMCP wraps as
`isError: true` with a text diagnostic, matching the REST 404 in
MCP's error idiom.

`subject_*` argument naming mirrors the REST query parameters and
the EvaluatePolicy dataclass for consistency.
"""

from collections.abc import Callable
from typing import Annotated, Literal
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.ports import Allow, Deny
from cora.trust._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.trust.features.evaluate_policy.handler import Handler
from cora.trust.features.evaluate_policy.query import EvaluatePolicy


class EvaluatePolicyOutput(BaseModel):
    """Structured output of the `evaluate_policy` MCP tool."""

    decision: Literal["Allow", "Deny"]
    reason: str | None = None


def register(mcp: FastMCP, *, get_handler: Callable[[], Handler]) -> None:
    """Register the `evaluate_policy` tool on the given MCP server."""

    @mcp.tool(
        name="evaluate_policy",
        description=(
            "Evaluate a specific Policy against a (principal, command, conduit) "
            "tuple and return Allow or Deny."
        ),
    )
    async def evaluate_policy_tool(  # pyright: ignore[reportUnusedFunction]
        policy_id: Annotated[
            UUID,
            Field(description="Target policy's id."),
        ],
        evaluated_principal_id: Annotated[
            UUID,
            Field(description="Principal whose authorization is being checked."),
        ],
        evaluated_command_name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=200,
                description="Command name being evaluated (e.g. 'RegisterActor').",
            ),
        ],
        evaluated_conduit_id: Annotated[
            UUID,
            Field(description="Conduit through which the command would be issued."),
        ],
    ) -> EvaluatePolicyOutput:
        handler = get_handler()
        result = await handler(
            EvaluatePolicy(
                policy_id=policy_id,
                evaluated_principal_id=evaluated_principal_id,
                evaluated_command_name=evaluated_command_name,
                evaluated_conduit_id=evaluated_conduit_id,
            ),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        if result is None:
            msg = f"Policy {policy_id} not found"
            raise ValueError(msg)
        if isinstance(result, Allow):
            return EvaluatePolicyOutput(decision="Allow")
        assert isinstance(result, Deny)  # pyright narrowing aid
        return EvaluatePolicyOutput(decision="Deny", reason=result.reason)
