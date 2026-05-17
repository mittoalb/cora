"""MCP tool for the `define_agent` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool. MCP tools currently bypass header extraction
and use `SYSTEM_PRINCIPAL_ID` directly until the MCP auth-flow
phase lands; for the same reason, `idempotency_key` defaults to None.
"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from cora.agent._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.agent.aggregates.agent import (
    AGENT_CANONICAL_URI_MAX_LENGTH,
    AGENT_CAPABILITIES_MAX_COUNT,
    AGENT_CAPABILITY_MAX_LENGTH,
    AGENT_DESCRIPTION_MAX_LENGTH,
    AGENT_KIND_MAX_LENGTH,
    AGENT_NAME_MAX_LENGTH,
    AGENT_VERSION_MAX_LENGTH,
    MODEL_REF_MODEL_MAX_LENGTH,
    MODEL_REF_PROVIDER_MAX_LENGTH,
    MODEL_REF_SNAPSHOT_PIN_MAX_LENGTH,
    ModelRef,
)
from cora.agent.features.define_agent.command import DefineAgent
from cora.agent.features.define_agent.handler import IdempotentHandler
from cora.infrastructure.observability import current_correlation_id


class ModelRefInput(BaseModel):
    """Sub-input for the typed ModelRef VO."""

    provider: str = Field(
        ...,
        min_length=1,
        max_length=MODEL_REF_PROVIDER_MAX_LENGTH,
        description="LLM provider name.",
    )
    model: str = Field(
        ...,
        min_length=1,
        max_length=MODEL_REF_MODEL_MAX_LENGTH,
        description="Provider-specific model identifier.",
    )
    snapshot_pin: str | None = Field(
        default=None,
        max_length=MODEL_REF_SNAPSHOT_PIN_MAX_LENGTH,
        description="Optional snapshot pin.",
    )


class DefineAgentOutput(BaseModel):
    """Structured output of the `define_agent` MCP tool."""

    agent_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the `define_agent` tool on the given MCP server."""

    @mcp.tool(
        name="define_agent",
        description=(
            "Define a new Agent (lands in Defined; co-registers an Actor with "
            "kind=agent atomically). Required: kind, name, version, model_ref. "
            "Optional: description, canonical_uri (https only), "
            "prompt_template_id, capabilities. The new agent_id is the same "
            "UUID as the co-registered Actor's id."
        ),
    )
    async def define_agent_tool(  # pyright: ignore[reportUnusedFunction]
        kind: Annotated[
            str,
            Field(
                min_length=1,
                max_length=AGENT_KIND_MAX_LENGTH,
                description="Agent kind discriminator (`RunDebrief`, etc.).",
            ),
        ],
        name: Annotated[
            str,
            Field(min_length=1, max_length=AGENT_NAME_MAX_LENGTH, description="Display name."),
        ],
        version: Annotated[
            str,
            Field(
                min_length=1,
                max_length=AGENT_VERSION_MAX_LENGTH,
                description="Version identifier.",
            ),
        ],
        model_ref: Annotated[
            ModelRefInput,
            Field(description="Model identity (provider + model + optional snapshot_pin)."),
        ],
        description: Annotated[
            str | None,
            Field(
                default=None,
                min_length=1,
                max_length=AGENT_DESCRIPTION_MAX_LENGTH,
                description="Optional description.",
            ),
        ] = None,
        canonical_uri: Annotated[
            str | None,
            Field(
                default=None,
                min_length=1,
                max_length=AGENT_CANONICAL_URI_MAX_LENGTH,
                description="Optional https canonical URI.",
            ),
        ] = None,
        prompt_template_id: Annotated[
            UUID | None,
            Field(default=None, description="Optional UUID into the prompt registry."),
        ] = None,
        capabilities: Annotated[
            list[str] | None,
            Field(
                default=None,
                max_length=AGENT_CAPABILITIES_MAX_COUNT,
                description=(
                    f"Optional capability claims (each 1-{AGENT_CAPABILITY_MAX_LENGTH} chars). "
                    "Null is treated as an empty set."
                ),
            ),
        ] = None,
    ) -> DefineAgentOutput:
        handler = get_handler()
        agent_id = await handler(
            DefineAgent(
                kind=kind,
                name=name,
                version=version,
                model_ref=ModelRef(
                    provider=model_ref.provider,
                    model=model_ref.model,
                    snapshot_pin=model_ref.snapshot_pin,
                ),
                description=description,
                canonical_uri=canonical_uri,
                prompt_template_id=prompt_template_id,
                capabilities=frozenset(capabilities or []),
            ),
            principal_id=SYSTEM_PRINCIPAL_ID,
            correlation_id=current_correlation_id(),
        )
        return DefineAgentOutput(agent_id=agent_id)
