# pyright: reportPrivateUsage=false

"""Architecture fitness: keep `_PrincipalKindLiteral` synced with `PrincipalKind`.

`cora.infrastructure.auth.config` defines a private `_PrincipalKindLiteral`
local mirror of `cora.infrastructure.ports.token_verifier.PrincipalKind`
to break the Settings ↔ auth.config import cycle (Settings imports
auth.config → which would import token_verifier → which triggers
ports/__init__.py → authorize → routing → observability → Settings).

The local mirror IS load-bearing (the alternative — direct import —
triggers the cycle, verified empirically at Iter B-1 gate review).
But mirrors drift. This fitness pins the value-set equality so a
PR that widens PrincipalKind (adds e.g. "automation") without also
widening _PrincipalKindLiteral fails CI at PR time, not at runtime
when a token from a new kind hits config-validation.

Per the cross-BC fitness convention: AST inspection rather than
runtime import (the runtime import would itself trigger part of the
cycle). We compare `typing.get_args` outputs on both literals.
"""

from typing import get_args

import pytest

from cora.infrastructure.auth.config import _PrincipalKindLiteral
from cora.infrastructure.ports.token_verifier import PrincipalKind


@pytest.mark.architecture
def test_auth_config_principal_kind_literal_matches_port() -> None:
    """The two Literal aliases MUST share the same value set.

    Drift here means `IdentityProviderConfig.principal_kind` would
    accept (or reject) values that the verifier's VerifiedPrincipal
    kind doesn't (or does). Either direction is a silent bug —
    config validation succeeds but verifier rejects, or vice versa.
    """
    config_kinds = set(get_args(_PrincipalKindLiteral))
    port_kinds = set(get_args(PrincipalKind))
    assert config_kinds == port_kinds, (
        f"_PrincipalKindLiteral and PrincipalKind have drifted: "
        f"config has {config_kinds}, port has {port_kinds}. "
        "Update both together — they exist as separate aliases only "
        "to break the Settings ↔ auth.config import cycle, not as "
        "an intentional value-set distinction."
    )
