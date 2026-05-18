"""BC-level bootstrap re-exports.

Mirrors the per-BC `_bootstrap` module convention. Today this module
exists solely to preserve the import path
`cora.calibration._bootstrap.SYSTEM_PRINCIPAL_ID` used by the MCP
tools. The constant itself lives at
`cora.infrastructure.routing.SYSTEM_PRINCIPAL_ID` (hoisted per the
all-BCs-share-one-canonical-home pattern).
"""

from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID

__all__ = ["SYSTEM_PRINCIPAL_ID"]
