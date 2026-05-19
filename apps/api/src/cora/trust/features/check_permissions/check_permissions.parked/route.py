"""HTTP route for the `check_permissions` query slice.

`POST /policies/{policy_id}/check` with a JSON body listing
`evaluated_principal_id`, `evaluated_conduit_id`, and a list of
commands to probe.

Returns 200 with `{"results": [{"command", "decision", "reason"}...]}`.
Both Allow and Deny rows are normal results — only a missing Policy
maps to 404.

POST is used (vs the GET that `evaluate_policy` uses) because the
batched-commands payload is too large/structured to fit cleanly as
query parameters. AuthZEN, AWS, GCP, and k8s all use POST for the
equivalent endpoints.
"""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import get_surface_id
from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id
from cora.trust.features.check_permissions.handler import Handler
from cora.trust.features.check_permissions.query import CheckPermissions

_MAX_COMMANDS = 50
_MAX_COMMAND_LENGTH = 128
_DISALLOWED_COMMAND_CHARS = ("*", "?")


class CheckPermissionsRequest(BaseModel):
    """Read-side DTO at the API boundary."""

    evaluated_principal_id: UUID = Field(
        description="Principal whose authorization is being probed."
    )
    evaluated_conduit_id: UUID = Field(
        description="Conduit through which the commands would be issued."
    )
    evaluated_commands: list[str] = Field(
        min_length=1,
        max_length=_MAX_COMMANDS,
        description=(
            "Commands to probe. 1..50 distinct command names; each 1..128 chars; "
            "no wildcards. Order is preserved into the response."
        ),
    )


class PermissionCheckResponse(BaseModel):
    """One probe result row."""

    command: str
    decision: Literal["allow", "deny"]
    reason: str | None = None


class CheckPermissionsResponse(BaseModel):
    """Top-level response: per-command probe results, ordered to match input."""

    results: list[PermissionCheckResponse]


def _validate_commands(commands: list[str]) -> tuple[str, ...]:
    """Reject empty/oversized/wildcarded/duplicate command names.

    Pydantic's `min_length` / `max_length` already gate the list size;
    this catches per-element rules + duplicate detection so the handler
    receives a clean tuple.
    """
    seen: set[str] = set()
    cleaned: list[str] = []
    for raw in commands:
        if not (1 <= len(raw) <= _MAX_COMMAND_LENGTH):
            msg = (
                f"command names must be 1..{_MAX_COMMAND_LENGTH} chars; "
                f"got {len(raw)}-char value"
            )
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=msg)
        for bad in _DISALLOWED_COMMAND_CHARS:
            if bad in raw:
                msg = f"wildcards not allowed in command names (got {raw!r})"
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=msg
                )
        if raw in seen:
            msg = f"duplicate command name in request: {raw!r}"
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=msg)
        seen.add(raw)
        cleaned.append(raw)
    return tuple(cleaned)


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.trust.check_permissions
    return handler


router = APIRouter(tags=["trust"])


@router.post(
    "/policies/{policy_id}/check",
    status_code=status.HTTP_200_OK,
    response_model=CheckPermissionsResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No policy exists with the given id.",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the query.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Body failed schema validation (empty / oversized / wildcarded / duplicate commands).",
        },
    },
    summary="Probe a Policy for permission to run each of N commands",
)
async def post_policies_check(
    policy_id: Annotated[UUID, Path(description="Target policy's id.")],
    body: CheckPermissionsRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> CheckPermissionsResponse:
    commands = _validate_commands(body.evaluated_commands)
    results = await handler(
        CheckPermissions(
            policy_id=policy_id,
            evaluated_principal_id=body.evaluated_principal_id,
            evaluated_conduit_id=body.evaluated_conduit_id,
            evaluated_commands=commands,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    if results is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy {policy_id} not found",
        )
    return CheckPermissionsResponse(
        results=[
            PermissionCheckResponse(command=r.command, decision=r.decision, reason=r.reason)
            for r in results
        ]
    )
