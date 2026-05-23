"""HTTP route for the `define_agent` slice.

`POST /agents` with body carrying kind / name / version / model_ref +
optional description / canonical_uri / prompt_template_id /
capabilities. Returns 201 + `{agent_id}` on success.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

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
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class ModelRefRequest(BaseModel):
    """Sub-body for the typed ModelRef VO."""

    provider: str = Field(
        ...,
        min_length=1,
        max_length=MODEL_REF_PROVIDER_MAX_LENGTH,
        description="LLM provider name (`anthropic`, `openai`, `google`, etc.).",
    )
    model: str = Field(
        ...,
        min_length=1,
        max_length=MODEL_REF_MODEL_MAX_LENGTH,
        description="Provider-specific model identifier (`claude-sonnet-4-6`, etc.).",
    )
    snapshot_pin: str | None = Field(
        default=None,
        max_length=MODEL_REF_SNAPSHOT_PIN_MAX_LENGTH,
        description=(
            "Optional provider-specific snapshot identifier (Anthropic snapshot "
            "string, OpenAI fingerprint, etc.) for reproducibility. Pass null "
            "to leave unpinned."
        ),
    )


class DefineAgentRequest(BaseModel):
    """Body for `POST /agents`."""

    kind: str = Field(
        ...,
        min_length=1,
        max_length=AGENT_KIND_MAX_LENGTH,
        description=(
            "Free-form agent kind discriminator (bare-str at MVP per Supply.kind "
            "precedent). Day-1 example: `RunDebriefer`."
        ),
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=AGENT_NAME_MAX_LENGTH,
        description="Human-readable display name.",
    )
    version: str = Field(
        ...,
        min_length=1,
        max_length=AGENT_VERSION_MAX_LENGTH,
        description="Semver-like version identifier (`v1`, `1.0.0`, etc.).",
    )
    model_ref: ModelRefRequest = Field(
        ...,
        description=(
            "Required model identity (provider + model + optional snapshot pin) "
            "so 8f-b's LLM has the identity available immediately."
        ),
    )
    description: str | None = Field(
        default=None,
        min_length=1,
        max_length=AGENT_DESCRIPTION_MAX_LENGTH,
        description="Optional free-form description.",
    )
    canonical_uri: str | None = Field(
        default=None,
        min_length=1,
        max_length=AGENT_CANONICAL_URI_MAX_LENGTH,
        description=(
            "Optional canonical https URI for A2A forward-compat. Must start "
            "with `https://` and contain no fragment."
        ),
    )
    prompt_template_id: UUID | None = Field(
        default=None,
        description=(
            "Optional UUID into the Python module registry at "
            "`cora.agent.prompts`. Required by 8f-b's RunDebriefer subscriber; "
            "may be null at 8f-a until the registry ships its first template."
        ),
    )
    capabilities: list[str] = Field(
        default_factory=list,
        max_length=AGENT_CAPABILITIES_MAX_COUNT,
        description=(
            f"Optional capability claims. Each entry 1-{AGENT_CAPABILITY_MAX_LENGTH} "
            "chars after trim. Empty list IS allowed."
        ),
    )


class DefineAgentResponse(BaseModel):
    """Response body for `POST /agents`."""

    agent_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.agent.define_agent
    return handler


router = APIRouter(tags=["agent"])


@router.post(
    "/agents",
    status_code=status.HTTP_201_CREATED,
    response_model=DefineAgentResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated (whitespace-only kind / name / version, "
                "over-cap capabilities, malformed canonical_uri, or invalid ModelRef)."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Defensive guard: the target Agent or co-written Actor stream "
                "already has events. Essentially impossible in production with "
                "UUIDv7 ids."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation (missing field, length "
                "out of bounds, invalid UUID), OR Idempotency-Key was reused "
                "with a different request body."
            ),
        },
    },
    summary="Define a new Agent (cross-BC atomic; co-registers an Actor with kind=agent)",
)
async def post_agents(
    body: DefineAgentRequest,
    handler: Annotated[IdempotentHandler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> DefineAgentResponse:
    agent_id = await handler(
        DefineAgent(
            kind=body.kind,
            name=body.name,
            version=body.version,
            model_ref=ModelRef(
                provider=body.model_ref.provider,
                model=body.model_ref.model,
                snapshot_pin=body.model_ref.snapshot_pin,
            ),
            description=body.description,
            canonical_uri=body.canonical_uri,
            prompt_template_id=body.prompt_template_id,
            capabilities=frozenset(body.capabilities),
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return DefineAgentResponse(agent_id=agent_id)
