"""MCP tool registration for the Recipe BC.

`register_recipe_tools(mcp, *, get_handlers)` registers each
slice's MCP tool on the shared FastMCP server. `get_handlers` is a
callable returning the `RecipeHandlers` bundle wired during the
FastAPI lifespan; it's invoked per tool call so the latest wiring
is always used.
"""

from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from cora.recipe.features.define_method import tool as define_method_tool
from cora.recipe.features.define_plan import tool as define_plan_tool
from cora.recipe.features.define_practice import tool as define_practice_tool
from cora.recipe.features.deprecate_method import tool as deprecate_method_tool
from cora.recipe.features.deprecate_plan import tool as deprecate_plan_tool
from cora.recipe.features.deprecate_practice import tool as deprecate_practice_tool
from cora.recipe.features.get_method import tool as get_method_tool
from cora.recipe.features.get_plan import tool as get_plan_tool
from cora.recipe.features.get_practice import tool as get_practice_tool
from cora.recipe.features.version_method import tool as version_method_tool
from cora.recipe.features.version_plan import tool as version_plan_tool
from cora.recipe.features.version_practice import tool as version_practice_tool
from cora.recipe.wire import RecipeHandlers


def register_recipe_tools(
    mcp: FastMCP,
    *,
    get_handlers: Callable[[], RecipeHandlers],
) -> None:
    """Register every Recipe slice's MCP tool on the FastMCP server."""
    define_method_tool.register(
        mcp,
        get_handler=lambda: get_handlers().define_method,
    )
    get_method_tool.register(
        mcp,
        get_handler=lambda: get_handlers().get_method,
    )
    version_method_tool.register(
        mcp,
        get_handler=lambda: get_handlers().version_method,
    )
    deprecate_method_tool.register(
        mcp,
        get_handler=lambda: get_handlers().deprecate_method,
    )
    define_practice_tool.register(
        mcp,
        get_handler=lambda: get_handlers().define_practice,
    )
    get_practice_tool.register(
        mcp,
        get_handler=lambda: get_handlers().get_practice,
    )
    version_practice_tool.register(
        mcp,
        get_handler=lambda: get_handlers().version_practice,
    )
    deprecate_practice_tool.register(
        mcp,
        get_handler=lambda: get_handlers().deprecate_practice,
    )
    define_plan_tool.register(
        mcp,
        get_handler=lambda: get_handlers().define_plan,
    )
    get_plan_tool.register(
        mcp,
        get_handler=lambda: get_handlers().get_plan,
    )
    version_plan_tool.register(
        mcp,
        get_handler=lambda: get_handlers().version_plan,
    )
    deprecate_plan_tool.register(
        mcp,
        get_handler=lambda: get_handlers().deprecate_plan,
    )
