"""Wire `Settings.identity_providers` → `IdentityProviderRegistry`.

Composition-root factory. Called once at lifespan start; the
resulting registry is held on the Kernel and injected into the
FastAPI/MCP middleware (Iter C). Tests build the registry directly
from `IdentityProviderConfig` instances via the helper to skip the
Settings layer.

## Why a factory module

Each `IdentityProviderConfig` entry could produce a JWTVerifier
adapter, an IntrospectionVerifier adapter, or both — depending on
which URLs the operator supplied. The registry takes the constructed
adapter instances; this module owns the "config row → adapter
instance(s)" translation so the registry stays a thin router.

Name matches the codebase factory convention (`agent/llm_factory.py`,
`trust/authorize_factory.py`). Originally named `registry_builder.py`
in Iter B-1 then renamed per impl-quality review #14 — `Builder`
in DDD vocabulary implies an incremental/fluent shape; this is a
one-shot `build_idp_registry(configs) -> IdentityProviderRegistry`
which is the Factory shape.

## Subject mapper

The factory takes a single SubjectMapper that all constructed
verifiers share (the Access BC owns one IdP-subject → Actor.id
mapping table across all IdPs). Iter B-1 ships `StaticSubjectMapper`
as the default; Iter B-2 swaps in the projection-backed mapper.
"""

from cora.infrastructure.auth.config import IdentityProviderConfig
from cora.infrastructure.auth.idp_registry import IdentityProviderRegistry
from cora.infrastructure.auth.introspection_verifier import IntrospectionVerifier
from cora.infrastructure.auth.jwt_verifier import JWTVerifier
from cora.infrastructure.ports.token_verifier import SubjectMapper


def build_idp_registry(
    identity_providers: list[IdentityProviderConfig],
    *,
    subject_mapper: SubjectMapper,
) -> IdentityProviderRegistry | None:
    """Construct an `IdentityProviderRegistry` from configured providers.

    Returns None when `identity_providers` is empty — callers (the
    lifespan code) treat None as "edge-auth disabled, fall through
    to the legacy X-Principal-Id path." This matches the existing
    `trust_policy_id: UUID | None = None` shape where None disables
    `TrustAuthorize` in favor of `AllowAllAuthorize`.

    Per the Iter A registry contract: at least ONE adapter must be
    constructed across all providers, or the registry constructor
    raises. An IdP entry can produce both a JWTVerifier AND an
    IntrospectionVerifier if both URLs are configured (uncommon but
    legitimate for IdPs that issue JWTs by default but need
    introspection for revocation-sensitive callers).

    Only ONE IntrospectionVerifier total is supported today (one per
    deployment — Globus, typically). A configuration with two
    introspection-providing IdPs raises ValueError: the registry's
    opaque-token routing can't disambiguate. JWT IdPs route by `iss`
    so any number is fine.
    """
    if not identity_providers:
        return None

    jwt_verifiers: list[JWTVerifier] = []
    introspection_verifier: IntrospectionVerifier | None = None

    for config in identity_providers:
        if config.jwks_url is not None:
            jwt_verifiers.append(
                JWTVerifier(
                    issuer=config.issuer,
                    jwks_url=config.jwks_url,
                    audience_for_surface=config.audiences,
                    subject_mapper=subject_mapper,
                    algorithms_allowed=config.algorithms_allowed,
                    principal_kind=config.principal_kind,
                    allow_insecure_jwks_url=config.allow_insecure_jwks_url,
                )
            )
        if config.introspection_url is not None:
            if introspection_verifier is not None:
                msg = (
                    f"build_idp_registry: more than one IdentityProviderConfig "
                    f"declares introspection_url (one for {introspection_verifier.issuer!r}, "
                    f"another for {config.issuer!r}). The registry's opaque-token "
                    "routing supports exactly one IntrospectionVerifier per "
                    "deployment today. If the deployment needs multi-IdP "
                    "introspection, the registry's opaque routing needs a "
                    "discriminator extension (token prefix per GitHub PAT "
                    "pattern) before this is removed."
                )
                raise ValueError(msg)
            # Iter B-1 narrow contract: introspection creds + url presence
            # validated by IdentityProviderConfig._introspection_creds_pair.
            # Explicit raise (not `assert`) so a future refactor that
            # breaks the validator doesn't silently UB under `python -O`.
            if config.introspection_client_id is None or config.introspection_client_secret is None:
                msg = (
                    f"build_idp_registry invariant violated: IdP {config.issuer!r} "
                    "has introspection_url but missing creds; "
                    "IdentityProviderConfig._introspection_creds_pair should have caught this."
                )
                raise RuntimeError(msg)
            introspection_verifier = IntrospectionVerifier(
                issuer=config.issuer,
                introspection_url=config.introspection_url,
                client_id=config.introspection_client_id,
                client_secret=config.introspection_client_secret,
                audience_for_surface=config.audiences,
                subject_mapper=subject_mapper,
                cache_ttl_seconds=config.introspection_cache_ttl_seconds,
                principal_kind=config.principal_kind,
                allow_insecure_introspection_url=config.allow_insecure_introspection_url,
            )

    return IdentityProviderRegistry(
        jwt_verifiers=jwt_verifiers,
        introspection_verifier=introspection_verifier,
    )


__all__ = ["build_idp_registry"]
