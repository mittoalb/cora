# Auth

For implementers wiring authentication and authorization. Each row names a role, the current pick, and the trigger that would force a swap. Edge authentication landed in Phase C (shipped 2026-05-19); the proxy-only contract is now a legacy fallback.

## Authentication

| Role | Pick | Why | Swap trigger |
| --- | --- | --- | --- |
| HTTP edge | `BearerAuthMiddleware` reading `Authorization: Bearer <token>` | Single ingress shape; standard RFC 6750 | Stays |
| Token verification | `TokenVerifier` port + `IdentityProviderRegistry` routing by `iss` claim | One registry per process, per-IdP verifier behind it | Stays |
| JWT path | `JWTVerifier` (PyJWT, JWKS + RFC 9068 profile) | OIDC IdPs that publish JWKS (Entra, Okta, Auth0) | Stays |
| Opaque-token path | `IntrospectionVerifier` (RFC 7662 introspection) | IdPs whose tokens are opaque (Globus Auth) | Stays |
| Subject mapping | `StaticSubjectMapper` (config-time `(issuer, subject) → actor_id`) | Pilot has bounded operator + agent set; explicit binding is auditable | Move to event-sourced `ActorIdpBindings` aggregate when first JIT-provisioning case lands |
| IdP metadata endpoint | RFC 9728 OAuth 2.0 Protected Resource Metadata at `/.well-known/oauth-protected-resource` | Lets clients discover accepted IdPs | Stays |
| Legacy fallback | `X-Principal-Id` header from a verifying proxy | Pre-Phase-C deployments; production refuses to boot without `REQUIRE_AUTHENTICATED_PRINCIPAL=true` | Removed once all fleets configure `IDENTITY_PROVIDERS` |

`get_principal_id` reads bearer-verified principals first (set by middleware on `request.state.principal`), then falls back to `X-Principal-Id` when no IdPs are configured. Bearer-mode 401s carry RFC 6750 `WWW-Authenticate: Bearer` challenges; introspection unavailability returns 503 + `Retry-After`.

## Authorization

| Role | Pick | Why | Swap trigger |
| --- | --- | --- | --- |
| `Authorize` port | Single `authorize(subject, command_name, conduit_id, surface_id) → AuthorizeDecision` | Surface_id threading lets one Policy bind to one surface (HTTP / MCP stdio / MCP streamable-http) | Stays |
| Policy engine | Trust BC `evaluate()` over current Policy aggregate | Inline; no external engine yet | First non-Cedar rule forces SpiceDB or OpenFGA |
| Authz model (planned) | ReBAC (SpiceDB or OpenFGA) | Multi-stakeholder ownership in shared facilities | Locked when first non-Cedar authz rule lands |
| Decision-BC policy language | Cedar | Used in Decision predicates (`has_determining_policies`) | Stays |
| Edge MCP gate | `mcp_gate` refuses write tools under prod posture | FastMCP 2025-11-25 spec gap; closes the door until A2A | First spec-level MCP auth verb lands |
