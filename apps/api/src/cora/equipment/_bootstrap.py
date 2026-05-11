"""BC-level bootstrap re-exports.

Today this module exists solely to preserve the import path
`cora.equipment._bootstrap.SYSTEM_PRINCIPAL_ID` used by Equipment's
MCP tools. The constant itself lives at
`cora.infrastructure.routing.SYSTEM_PRINCIPAL_ID` since the
post-Phase-3 cleanup hoisted both BCs' identical fallback constants
to one canonical home.

Future Equipment-specific BC-level constants (none today) would land
here and join the re-exports below.
"""

from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID

__all__ = ["SYSTEM_PRINCIPAL_ID"]
