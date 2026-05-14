"""HTTP route for the `update_method_parameters_schema` slice.

Action endpoint at `POST /methods/{method_id}/parameters-schema`.
Body carries the JSON Schema (or null to clear). 204 No Content on
success. Same action-endpoint pattern as `update_capability_settings_schema`
(Equipment 5g-a) and the other transition slices.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id
from cora.recipe.features.update_method_parameters_schema.command import (
    UpdateMethodParametersSchema,
)
from cora.recipe.features.update_method_parameters_schema.handler import Handler


class UpdateMethodParametersSchemaRequest(BaseModel):
    """Body for `POST /methods/{method_id}/parameters-schema`."""

    parameters_schema: dict[str, Any] | None = Field(
        ...,
        description=(
            "JSON Schema (Draft 2020-12, constrained subset) declaring "
            "the shape of parameter dicts that downstream Plans (6g-b) "
            "and Runs (6g-c) carry for this Method. Pass `null` to "
            "clear an existing schema. Subset allows only: $schema, "
            "type, required, properties, enum, minimum, maximum, "
            "pattern. The $schema field is required (must be "
            "'https://json-schema.org/draft/2020-12/schema')."
        ),
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.recipe.update_method_parameters_schema
    return handler


router = APIRouter(tags=["recipe"])


@router.post(
    "/methods/{method_id}/parameters-schema",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Schema rejected: missing or wrong `$schema`, forbidden "
                "keyword (e.g. $ref / oneOf / allOf), or jsonschema-rs "
                "rejected the schema as malformed."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No method exists with the given id.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Concurrent write to the same method stream conflicted (optimistic concurrency)."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter or request body failed schema validation.",
        },
    },
    summary="Set, replace, or clear a Method's parameters_schema",
)
async def post_methods_parameters_schema(
    method_id: Annotated[UUID, Path(description="Target method's id.")],
    body: UpdateMethodParametersSchemaRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
) -> None:
    await handler(
        UpdateMethodParametersSchema(
            method_id=method_id,
            parameters_schema=body.parameters_schema,
        ),
        principal_id=principal_id,
        correlation_id=cid,
    )
