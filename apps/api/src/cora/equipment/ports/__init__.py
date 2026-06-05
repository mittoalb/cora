"""Equipment BC ports (BC-tier Protocols owned by Equipment).

`DoiMinter` ships here per [[project-asset-persistent-id-write-design]]
(slice F.1): the operator-facing surface for minting a PIDINST v1.0
Property 1 persistent identifier (DOI or Handle) at an external
authority such as DataCite or Handle.net.

BC-tier port location per [[project-adapter-naming-design]]: stays
here until rule-of-three promotes to `cora.infrastructure.ports`.
"""

from cora.equipment.ports.doi_minter import (
    DoiMinter,
    PersistentIdentifierMintError,
)

__all__ = [
    "DoiMinter",
    "PersistentIdentifierMintError",
]
