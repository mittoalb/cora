"""BC-level bootstrap re-exports for the Decision BC's MCP tools.

The constant itself lives at `cora.infrastructure.routing.SYSTEM_PRINCIPAL_ID`
(one canonical fallback). Future Decision-specific BC-level
constants would land here and join the re-exports below.
"""

from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID

__all__ = ["SYSTEM_PRINCIPAL_ID"]
