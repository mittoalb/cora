"""MCP tool for the `register_fixture` slice."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.equipment.aggregates.fixture import SlotAssetBinding
from cora.equipment.features.register_fixture.command import RegisterFixture
from cora.equipment.features.register_fixture.handler import IdempotentHandler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class SlotAssetBindingInput(BaseModel):
    """A single slot-to-asset binding within the tool input."""

    slot_name: str = Field(min_length=1, max_length=100)
    asset_id: UUID

    def to_domain(self) -> SlotAssetBinding:
        return SlotAssetBinding(slot_name=self.slot_name, asset_id=self.asset_id)


class RegisterFixtureOutput(BaseModel):
    fixture_id: UUID


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    @mcp.tool(
        name="register_fixture",
        description=(
            "Register a Fixture: materialize an existing Assembly "
            "blueprint into a concrete cluster of pre-existing Assets. "
            "Returns the new fixture_id. The N referenced Assets are "
            "NOT created by this call; they must be registered first "
            "via register_asset. Slot cardinality, Family-set "
            "intersection, and parameter_overrides schema validation "
            "all enforced at registration time. Note: this MCP surface "
            "has no idempotency-key equivalent of the REST "
            "Idempotency-Key header; retries of a failed or lost call "
            "may create duplicate Fixtures."
        ),
    )
    async def register_fixture_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        assembly_id: Annotated[
            UUID,
            Field(description="Target Assembly's id."),
        ],
        slot_asset_bindings: Annotated[
            list[SlotAssetBindingInput],
            Field(
                description=(
                    "Bindings of slot_name to pre-existing Asset.id. "
                    "Each binding's slot_name must reference a "
                    "TemplateSlot on the Assembly; each asset_id must "
                    "resolve to a registered Asset whose family_ids "
                    "intersect the slot's required_family_ids."
                ),
            ),
        ] = [],  # noqa: B006
        parameter_overrides: Annotated[
            dict[str, Any],
            Field(
                description=(
                    "Operator-supplied parameter overrides validated "
                    "against the Assembly's parameter_overrides_schema."
                ),
            ),
        ] = {},  # noqa: B006
    ) -> RegisterFixtureOutput:
        handler = get_handler()
        fixture_id = await handler(
            RegisterFixture(
                assembly_id=assembly_id,
                slot_asset_bindings=frozenset(b.to_domain() for b in slot_asset_bindings),
                parameter_overrides=parameter_overrides,
                surface_id=get_mcp_surface_id(),
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RegisterFixtureOutput(fixture_id=fixture_id)
