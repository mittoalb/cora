# Surfaces

*Surfaces, handlers, cross-cutting concerns.*

Every command and query has one handler and as many surface adapters as needed. A new surface is a new adapter; the core does not move. For the adapters in service today, see [Stack/Backend](../stack/backend.md).

## Cross-cutting

- **Idempotency.** Create-style commands accept an idempotency key. The store remembers `(key, command_name, body_hash) → result` and replays on retry.
- **Authentication.** Verified principal-id header from an upstream proxy. The proxy strips client-supplied headers and sets the verified value; production refuses to boot without one.
- **Authorization.** Every command and query passes an `Authorize` port. Policy model is ReBAC, with cross-principal contract tests (BOLA) per read endpoint.
- **Observability.** Structured logs, distributed tracing, and metrics on every handler. Trace context is the source of truth for correlation id.
- **Migrations.** Forward-only. A rollback is a new compensating migration. CI verifies hash-sum integrity and runs a safety scan on net-new migrations.
