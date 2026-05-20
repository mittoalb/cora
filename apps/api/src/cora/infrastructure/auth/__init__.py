"""Phase C edge-auth adapter package.

Implementations of `cora.infrastructure.ports.TokenVerifier`:

  - `JWTVerifier` — local JWKS-based JWT verify (RFC 9068).
  - `IntrospectionVerifier` — RFC 7662 token introspection.
  - `IdentityProviderRegistry` — process-singleton routing inbound
    tokens to the right verifier per their issuer.

Per the Phase C design lock library-vs-DIY decision: PyJWT is the
one library dependency; everything else is hand-written.
"""

from cora.infrastructure.auth.config import (
    IdentityProviderConfig,
    IdpSubjectBinding,
    StaticSubjectMapper,
    build_static_subject_mapper,
)
from cora.infrastructure.auth.idp_registry import IdentityProviderRegistry
from cora.infrastructure.auth.introspection_verifier import IntrospectionVerifier
from cora.infrastructure.auth.jwt_verifier import JWTVerifier
from cora.infrastructure.auth.registry_factory import build_idp_registry

# NB: `BearerAuthMiddleware` (apps/api/src/cora/infrastructure/auth/
# bearer_middleware.py) is intentionally NOT re-exported from this
# package init. Re-exporting it would import bearer_middleware at
# auth-package load time, which triggers a cycle: Settings ->
# auth.config -> auth.__init__ -> bearer_middleware -> routing
# (mid-load, on the path that started this whole chain via
# observability -> Settings). main.py imports
# `from cora.infrastructure.auth.bearer_middleware import
# BearerAuthMiddleware` directly to side-step the package init.
__all__ = [
    "IdentityProviderConfig",
    "IdentityProviderRegistry",
    "IdpSubjectBinding",
    "IntrospectionVerifier",
    "JWTVerifier",
    "StaticSubjectMapper",
    "build_idp_registry",
    "build_static_subject_mapper",
]
