"""Settings-loadable schema for Phase C edge-auth identity providers.

Defines the typed shape that `Settings.identity_providers` carries
(loaded from env vars in `cora.infrastructure.config.Settings`).
Production deployments configure one entry per IdP that mints tokens
for CORA — Globus Auth (introspection-only), Microsoft Entra (JWT),
etc.

Also defines `StaticSubjectMapper`, the Iter B-1 SubjectMapper
implementation. Holds a fixed `(issuer, subject) → (principal_id, kind)`
dict — sufficient for small deployments (single beamline, ~10 humans
+ 1-2 service accounts). Iter B-2 ships the projection-backed
`ActorIdpBindingsSubjectMapper` for larger deployments that mint
Actors at runtime.

## Why two mappers (precedent)

Same pattern Tiled (BNL data server) uses: static dict for
small/test deployments, OIDC-projection-backed for big ones. Both
satisfy `cora.infrastructure.ports.token_verifier.SubjectMapper`,
so the registry doesn't know or care which is wired.
"""

from collections.abc import Mapping
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, SecretStr, model_validator

# Local Literal alias to avoid a top-level import from
# `cora.infrastructure.ports.token_verifier`. That import would
# trigger a cycle: Settings (cora.infrastructure.config) needs this
# IdentityProviderConfig, and ports.token_verifier transitively
# imports through observability back to Settings. The values MUST
# stay in sync with `PrincipalKind` on the port; the static
# `StaticSubjectMapper` below imports the port lazily inside its
# method (signature uses the local alias too).
_PrincipalKindLiteral = Literal["human", "service_account"]


class IdentityProviderConfig(BaseModel):
    """Per-IdP configuration loaded from `Settings.identity_providers`.

    Each entry binds a single OIDC issuer URL to either a JWT path
    (jwks_url required) or an introspection path (introspection_url
    + introspection_client_id + introspection_client_secret required),
    or both (introspection used for revocation-sensitive callers).

    The `audiences` map binds the 3 SYSTEM Surface UUIDs to the
    audience strings the IdP signs into the token's `aud` claim for
    that Surface. CORA registers itself with the IdP using these
    audience strings; the IdP issues tokens with `aud=<the one for
    the Surface the caller wants to reach>`.

    `allow_insecure_*_url` opt-ins exist for test/dev fixtures that
    use localhost endpoints; production deployments leave these
    False so the constructor rejects http:// URLs (gate-review F2).
    """

    issuer: str = Field(
        ...,
        description=(
            "OIDC issuer URL — exact match against the 'iss' claim on "
            "every token. Must match the IdP's published metadata; "
            "trailing-slash lenient matching is NOT performed (matches "
            "RFC 9068 §4 expectation that iss is exact-match)."
        ),
    )

    jwks_url: str | None = Field(
        default=None,
        description=(
            "JWKS endpoint URL. Required when the IdP issues JWT access "
            "tokens (Microsoft Entra, Google, Auth0, Okta, AWS Cognito, "
            "Helmholtz AAI). Leave None for introspection-only IdPs "
            "(Globus Auth default)."
        ),
    )

    introspection_url: str | None = Field(
        default=None,
        description=(
            "RFC 7662 introspection endpoint URL. Required for IdPs that "
            "issue opaque tokens (Globus Auth) or when revocation must "
            "be checked per-request. Triggers the IntrospectionVerifier "
            "adapter path."
        ),
    )

    introspection_client_id: str | None = Field(
        default=None,
        description=(
            "OAuth client id CORA presents to the IdP's introspection "
            "endpoint via HTTP Basic. Required when introspection_url "
            "is set. Distinct from the user-facing client_id."
        ),
    )

    introspection_client_secret: SecretStr | None = Field(
        default=None,
        description=(
            "OAuth client secret paired with introspection_client_id. "
            "Required when introspection_url is set. SecretStr keeps it "
            "out of logs / __repr__ / model_dump_json."
        ),
    )

    audiences: dict[UUID, str] = Field(
        default_factory=lambda: {},
        description=(
            "Surface UUID → audience string. CORA registers the audience "
            "strings with the IdP at deployment; the IdP signs them into "
            "the 'aud' claim. Per RFC 8707 §3 each Surface gets a "
            "distinct audience so cross-Surface token replay fails."
        ),
    )

    algorithms_allowed: list[str] = Field(
        default_factory=lambda: ["RS256", "ES256"],
        description=(
            "JWT signature algorithms accepted by the JWTVerifier. "
            "Default ['RS256', 'ES256'] covers every mature OIDC IdP. "
            "Per AH4 the constructor rejects 'none' in any case."
        ),
    )

    principal_kind: _PrincipalKindLiteral = Field(
        default="human",
        description=(
            "Default kind applied to VerifiedPrincipal when the "
            "SubjectMapper doesn't override it. Override per-IdP for "
            "deployments where the entire IdP issues only service-"
            "account tokens (e.g. a CI-only client_credentials IdP)."
        ),
    )

    introspection_cache_ttl_seconds: int = Field(
        default=30,
        ge=1,
        description=(
            "Per-token introspection cache lifetime. Lower for stronger "
            "revocation, higher for less IdP load (gate-review tradeoff). "
            "AH12 forbids 0."
        ),
    )

    allow_insecure_jwks_url: bool = Field(
        default=False,
        description=(
            "Production MUST be False. Test/dev fixtures using "
            "http://127.0.0.1:... opt in; otherwise constructor "
            "rejects http:// (gate-review F2)."
        ),
    )

    allow_insecure_introspection_url: bool = Field(
        default=False,
        description=(
            "Production MUST be False. Same shape as "
            "allow_insecure_jwks_url; without HTTPS the introspection "
            "POST leaks CORA's client_secret to MITM."
        ),
    )

    @model_validator(mode="after")
    def _at_least_one_verification_path(self) -> "IdentityProviderConfig":
        """An IdP entry must provide at least one verification path
        (JWT, introspection, or both). An entry with neither would
        never authenticate any token from this issuer."""
        if self.jwks_url is None and self.introspection_url is None:
            msg = (
                f"IdentityProviderConfig for issuer={self.issuer!r} "
                "must specify jwks_url (JWT path) OR introspection_url "
                "(opaque path), or both. An entry with neither cannot "
                "authenticate any token."
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _introspection_creds_pair(self) -> "IdentityProviderConfig":
        """introspection_url requires both client_id and client_secret."""
        if self.introspection_url is not None and (
            self.introspection_client_id is None or self.introspection_client_secret is None
        ):
            msg = (
                f"IdentityProviderConfig for issuer={self.issuer!r}: "
                "introspection_url requires both introspection_client_id "
                "and introspection_client_secret (RFC 7662 §2.1 HTTP "
                "Basic auth)."
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _audiences_non_empty(self) -> "IdentityProviderConfig":
        """Audiences map MUST have at least one entry (gate-review F12).

        An IdP entry with `audiences={}` validates structurally but
        produces a verifier that rejects every request with
        `wrong_audience` — a fail-late mode that violates the
        module-docstring promise of fail-fast startup validation.
        Operators get a 401 with no clue why; this validator names
        the missing config explicitly.
        """
        if not self.audiences:
            msg = (
                f"IdentityProviderConfig for issuer={self.issuer!r}: "
                "audiences map must have at least one Surface UUID → "
                "audience-string entry. An empty map produces a verifier "
                "that rejects every request with wrong_audience. Map at "
                "least one of the SYSTEM Surface UUIDs (HTTP=...0020, "
                "MCP_STDIO=...0021, MCP_STREAMABLE_HTTP=...0022) to the "
                "audience string the IdP signs into the 'aud' claim."
            )
            raise ValueError(msg)
        return self


class StaticSubjectMapper:
    """SubjectMapper backed by an in-memory `(issuer, subject) → (id, kind)` dict.

    Sufficient for small deployments (single beamline pilot, ~10
    humans + 1-2 service accounts) where the Actor set is fixed at
    deployment time and rarely changes.

    Iter B-2 ships `ActorIdpBindingsSubjectMapper` which queries an
    access-projection table for deployments with dynamic Actor
    registration. Both satisfy the SubjectMapper protocol; the
    registry doesn't care.

    Per the design memo's `unknown_subject` reason: an `(iss, sub)`
    not in the map raises `InvalidTokenError("unknown_subject", ...)`
    — the verifier's `safe_map_subject` helper would wrap a raw
    exception, but we raise the typed error directly so the route
    layer sees a clean 401 with the right reason code.
    """

    def __init__(
        self,
        bindings: Mapping[tuple[str, str], tuple[UUID, _PrincipalKindLiteral]],
    ) -> None:
        """Construct with a fixed binding mapping.

        Keys: `(issuer, subject)` tuple. Both strings exact-match.
        Values: `(principal_id, kind)` tuple.

        Accepts any `Mapping` for the immutable-interface convention
        widespread in the codebase (json_merge_patch.py, recipe/plan/
        parameters_validation.py). The mapping is defensive-copied
        into an internal dict at construction so callers can't mutate
        live auth behavior between requests (gate-review impl#10).

        Usage:
            mapper = StaticSubjectMapper({
                ("https://idp.example.com", "user-abc"): (UUID(...), "human"),
                ("https://idp.example.com", "ci-bot"): (UUID(...), "service_account"),
            })
        """
        self._bindings: dict[tuple[str, str], tuple[UUID, _PrincipalKindLiteral]] = dict(bindings)

    async def __call__(self, issuer: str, subject: str) -> tuple[UUID, _PrincipalKindLiteral]:
        # Lazy import to avoid the Settings ↔ auth.config cycle (see
        # `_PrincipalKindLiteral` docstring above).
        from cora.infrastructure.ports.token_verifier import InvalidTokenError

        mapping = self._bindings.get((issuer, subject))
        if mapping is None:
            raise InvalidTokenError(
                "unknown_subject",
                f"no Actor mapped for issuer={issuer!r} subject={subject!r}",
            )
        return mapping


__all__ = ["IdentityProviderConfig", "StaticSubjectMapper"]
