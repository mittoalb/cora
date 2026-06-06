"""Pure decider for the `RemoveMethodRequiredRole` command.

Three disqualifying conditions surface as dedicated error classes:

  - Method stream has no events -> `MethodNotFoundError` (404)
  - Method status is not `Defined` -> `MethodCannotMutateRequiredRolesError`
    (409). Same guard as `add_method_required_role`: a Versioned
    Method has an attested content_hash, a Deprecated Method is out
    of use entirely.
  - `command.role_name` not in `state.required_roles` ->
    `MethodRoleNameNotFoundError` (404, strict-not-idempotent).

Mirror of `add_method_required_role`: the lifecycle guard error
class is shared (`MethodCannotMutateRequiredRolesError`) because the
guard is symmetric.

The `RoleName` VO validates its own bounded text in `__post_init__`;
reaching the decider means the VO is already shape-valid.
"""

from datetime import datetime

from cora.recipe.aggregates.method import (
    Method,
    MethodCannotMutateRequiredRolesError,
    MethodNotFoundError,
    MethodRequiredRoleRemoved,
    MethodRoleNameNotFoundError,
    MethodStatus,
)
from cora.recipe.features.remove_method_required_role.command import (
    RemoveMethodRequiredRole,
)


def decide(
    state: Method | None,
    command: RemoveMethodRequiredRole,
    *,
    now: datetime,
) -> list[MethodRequiredRoleRemoved]:
    """Decide the events produced by removing a required role.

    Invariants:
      - State must not be None -> MethodNotFoundError
      - State.status must be Defined -> MethodCannotMutateRequiredRolesError
      - command.role_name must already be present in state.required_roles
        (keyed on role_name; strict-not-idempotent) ->
        MethodRoleNameNotFoundError
    """
    if state is None:
        raise MethodNotFoundError(command.method_id)

    if state.status is not MethodStatus.DEFINED:
        raise MethodCannotMutateRequiredRolesError(state.id, state.status)

    if not any(existing.role_name == command.role_name for existing in state.required_roles):
        raise MethodRoleNameNotFoundError(state.id, command.role_name)

    return [
        MethodRequiredRoleRemoved(
            method_id=state.id,
            role_name=command.role_name.value,
            occurred_at=now,
        )
    ]
