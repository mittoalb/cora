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
from cora.recipe.features.get_method import tool as get_method_tool
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
