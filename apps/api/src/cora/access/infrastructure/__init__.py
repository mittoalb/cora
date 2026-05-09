"""Access infrastructure: REST routes, MCP tools, BC-specific adapters.

Public surface:
    - register_access_routes(app)  -- attach REST endpoints + exception handlers

Phase 1f will add the MCP tool registration alongside.
"""

from cora.access.infrastructure.routes import register_access_routes

__all__ = ["register_access_routes"]
