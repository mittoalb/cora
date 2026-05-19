"""Phase C edge-auth adapter package.

Implementations of `cora.infrastructure.ports.TokenVerifier`:

  - `JWTVerifier` — local JWKS-based JWT verify (RFC 9068).
  - `IntrospectionVerifier` — RFC 7662 token introspection.
  - `IdentityProviderRegistry` — process-singleton routing inbound
    tokens to the right verifier per their issuer.

Per the Phase C design lock library-vs-DIY decision: PyJWT is the
one library dependency; everything else is hand-written.
"""

from cora.infrastructure.auth.config import IdentityProviderConfig, StaticSubjectMapper
from cora.infrastructure.auth.idp_registry import IdentityProviderRegistry
from cora.infrastructure.auth.introspection_verifier import IntrospectionVerifier
from cora.infrastructure.auth.jwt_verifier import JWTVerifier
from cora.infrastructure.auth.registry_builder import build_idp_registry

__all__ = [
    "IdentityProviderConfig",
    "IdentityProviderRegistry",
    "IntrospectionVerifier",
    "JWTVerifier",
    "StaticSubjectMapper",
    "build_idp_registry",
]
