"""BC-level bootstrap re-exports for the Recipe BC.

Mirrors `cora.equipment._bootstrap`. Today this module exists solely
to preserve the import path `cora.recipe._bootstrap.SYSTEM_PRINCIPAL_ID`
used by Recipe's MCP tools. The constant itself lives at
`cora.infrastructure.routing.SYSTEM_PRINCIPAL_ID` since the
post-Phase-3 cleanup hoisted both BCs' identical fallback constants
to one canonical home.

Future Recipe-specific BC-level constants (none today) would land
here and join the re-exports below.
"""

from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID

__all__ = ["SYSTEM_PRINCIPAL_ID"]
