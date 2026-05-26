"""Edge-auth plumbing package.

Holds the auth-edge pieces that are NOT `TokenVerifier` port adapters:

  - `BearerAuthMiddleware` (Starlette middleware) — verifies inbound
    `Authorization: Bearer` tokens via the kernel's configured verifier.
  - `IdentityProviderRegistry` — process-singleton router that picks the
    right `TokenVerifier` adapter per token's issuer.
  - `IdentityProviderConfig` + `IdpSubjectBinding` + `StaticSubjectMapper`
    — config + subject-mapping helpers.
  - `build_idp_registry`, `build_static_subject_mapper` — composition-root
    factories.
  - `exception_handlers.py` — FastAPI exception handler functions that
    convert auth errors into RFC 6750 401 / RFC 7231 503 responses.

The `TokenVerifier` port adapters themselves live at
`cora.infrastructure.adapters.jwt_token_verifier::JwtTokenVerifier` and
`cora.infrastructure.adapters.introspection_token_verifier::IntrospectionTokenVerifier`
per the locked `<Tech><Port>` naming rule.

Per the edge-auth design lock library-vs-DIY decision: PyJWT is the
one library dependency; everything else is hand-written.
"""

from cora.infrastructure.auth.build_idp_registry import build_idp_registry
from cora.infrastructure.auth.config import (
    IdentityProviderConfig,
    IdpSubjectBinding,
    StaticSubjectMapper,
    build_static_subject_mapper,
)
from cora.infrastructure.auth.idp_registry import IdentityProviderRegistry

# NB: `BearerAuthMiddleware` (apps/api/src/cora/infrastructure/auth/
# bearer_auth_middleware.py) is intentionally NOT re-exported from this
# package init. Re-exporting it would import bearer_auth_middleware at
# auth-package load time, which triggers a cycle: Settings ->
# auth.config -> auth.__init__ -> bearer_auth_middleware -> routing
# (mid-load, on the path that started this whole chain via
# observability -> Settings). main.py imports
# `from cora.infrastructure.auth.bearer_auth_middleware import
# BearerAuthMiddleware` directly to side-step the package init.
__all__ = [
    "IdentityProviderConfig",
    "IdentityProviderRegistry",
    "IdpSubjectBinding",
    "StaticSubjectMapper",
    "build_idp_registry",
    "build_static_subject_mapper",
]
