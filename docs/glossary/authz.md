# Authz terms

*ReBAC, BOLA, Cedar, principal, actor vs profile.*

- **ReBAC.** Relationship-based access control (planned: SpiceDB or OpenFGA). For multi-stakeholder ownership common in shared facilities.
- **BOLA.** Broken Object-Level Authorization (OWASP API #1). Covered by a parametrized cross-principal contract test on every read endpoint.
- **Cedar.** Policy language used in `decision` BC predicates.
- **Principal.** Authenticated identity attached to every command and event envelope. Required in production via `REQUIRE_AUTHENTICATED_PRINCIPAL=true`.
- **Actor vs Profile.** `Actor` is the immutable identity in events; `Profile` is the mutable PII row, separately stored and erasable. GDPR-shaped.
