"""Architecture fitness: keep ActorKind value set in sync across DTO Literals + SQL CHECK.

The closed set `{human, agent, service_account}` is hardcoded in
SIX places that MUST stay in sync:

  1. `cora.access.aggregates.actor.state.ActorKind` (StrEnum, source of truth)
  2. `cora.access.features.list_actors.handler._KindLiteral`
  3. `cora.access.features.list_actors.route.ActorSummaryDTO.kind`
  4. `cora.access.features.list_actors.tool.ActorSummaryRow.kind`
  5. `cora.access.features.get_actor.route.ActorResponse.kind`
  6. `cora.access.features.get_actor.tool.ActorOutput.kind`

(The SQL CHECK constraint lives in migration
20260519233000_widen_proj_access_actor_summary_kind.sql; verified
by integration tests against real Postgres.)

A SEVENTH place — `cora.infrastructure.ports.token_verifier.PrincipalKind`
— intentionally carries a SUBSET of ActorKind (`{human,
service_account}`, no `agent`). Agents-as-callers authenticate via
client_credentials and look like service_accounts on the wire;
ActorKind.AGENT is a registration-provenance marker, not a wire
principal kind. This fitness pins both the equality between the
six DTO sites AND the subset relationship with PrincipalKind so a
future widening doesn't drift either invariant.

Gate-review history: Iter B-2's first ship missed widening the
get_actor DTOs (sites #5 + #6), shipping a 500 fail-late for any
service_account Actor fetch. This fitness catches that class of
drift at PR time.
"""

# pyright: reportPrivateUsage=false

from typing import get_args

import pytest

from cora.access.aggregates.actor.state import ActorKind
from cora.access.features.get_actor.route import ActorResponse as GetActorResponse
from cora.access.features.get_actor.tool import ActorOutput as GetActorOutput
from cora.access.features.list_actors.handler import _KindLiteral
from cora.access.features.list_actors.route import ActorSummaryDTO
from cora.access.features.list_actors.tool import ActorSummaryRow
from cora.infrastructure.ports.token_verifier import PrincipalKind


def _literal_args_of_kind_field(model: type) -> tuple[str, ...]:
    """Pull the Literal[...] args off a Pydantic model's `kind` field."""
    field_info = model.model_fields["kind"]  # type: ignore[attr-defined]
    return tuple(get_args(field_info.annotation))  # type: ignore[no-any-return]


@pytest.mark.architecture
def test_actor_kind_enum_canonical_value_set() -> None:
    """Source-of-truth check: ActorKind contains exactly the 3 values."""
    assert {k.value for k in ActorKind} == {"human", "agent", "service_account"}


@pytest.mark.architecture
def test_list_actors_handler_literal_matches_actor_kind() -> None:
    # `type _KindLiteral = Literal[...]` is a PEP 695 TypeAliasType;
    # `get_args` returns empty on it directly. Reach the wrapped
    # Literal via `__value__`.
    underlying = _KindLiteral.__value__  # type: ignore[attr-defined]
    assert set(get_args(underlying)) == {k.value for k in ActorKind}


@pytest.mark.architecture
def test_list_actors_route_dto_literal_matches_actor_kind() -> None:
    assert set(_literal_args_of_kind_field(ActorSummaryDTO)) == {k.value for k in ActorKind}


@pytest.mark.architecture
def test_list_actors_tool_dto_literal_matches_actor_kind() -> None:
    assert set(_literal_args_of_kind_field(ActorSummaryRow)) == {k.value for k in ActorKind}


@pytest.mark.architecture
def test_get_actor_route_dto_literal_matches_actor_kind() -> None:
    """Gate-review BLOCKING: Iter B-2 first-ship missed this site."""
    assert set(_literal_args_of_kind_field(GetActorResponse)) == {k.value for k in ActorKind}


@pytest.mark.architecture
def test_get_actor_tool_dto_literal_matches_actor_kind() -> None:
    """Gate-review BLOCKING: Iter B-2 first-ship missed this site."""
    assert set(_literal_args_of_kind_field(GetActorOutput)) == {k.value for k in ActorKind}


@pytest.mark.architecture
def test_principal_kind_is_subset_of_actor_kind() -> None:
    """PrincipalKind intentionally omits 'agent' (agents-as-callers
    authenticate as service_accounts; ActorKind.AGENT is a
    registration-provenance marker only). Pin the subset relationship
    so any future PrincipalKind widening that adds a value not in
    ActorKind fails CI."""
    principal_kinds = set(get_args(PrincipalKind))
    actor_kinds = {k.value for k in ActorKind}
    assert principal_kinds <= actor_kinds, (
        f"PrincipalKind {principal_kinds - actor_kinds} not in ActorKind {actor_kinds}. "
        "Widen ActorKind first, then PrincipalKind."
    )


@pytest.mark.architecture
def test_principal_kind_excludes_agent_intentionally() -> None:
    """Documentation-as-test for the intentional asymmetry. If a future
    PR adds 'agent' to PrincipalKind, this fails — forcing the author
    to update the design memo (project_edge_auth_design Decision 5 +
    Decision 9 asymmetry rationale) before the closed set widens."""
    assert "agent" not in set(get_args(PrincipalKind)), (
        "PrincipalKind intentionally excludes 'agent' — agents authenticate "
        "as service_accounts via client_credentials. If you want to add 'agent', "
        "update project_edge_auth_design's Decision 5/9 rationale first."
    )
