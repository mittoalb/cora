# Surfaces

*REST, agent protocol, cross-cutting concerns.*

Every command is exposed on two equivalent surfaces, same handler:

- **REST.** HTTP, OpenAPI-described.
- **Agent protocol.** For LLM-driven agents. Same handler, different transport.

The handler is the unit of authoritative behaviour. A third surface (A2A, gRPC) is a third adapter; the core does not move.

## Same command, two surfaces

`RegisterActor` exposed as REST and MCP, both call the same `register_actor.bind(deps)` handler:

```bash
# REST
curl -X POST /actors -H 'Content-Type: application/json' \
  -d '{"name": "Doga"}'
# -> 201 {"actor_id": "01900000-..."}
```

```jsonc
// MCP tools/call
{ "name": "register_actor", "arguments": { "name": "Doga" } }
// -> structured content { "actor_id": "01900000-..." }
```

Domain rule, ID generation, audit, authz, idempotency all run once in the handler. Routes and tools are thin schema adapters.

## Cross-cutting

- **Idempotency.** Create-style commands accept an `Idempotency-Key` header (IETF draft). Store remembers `(key, command_name, body_hash) → result`, replays on retry.
- **Authentication.** App trusts `X-Principal-Id` set by an upstream verifying proxy. Production must front the API with a proxy that strips client-supplied headers and sets the verified value.
- **Authorisation.** Every command and query passes an `Authorize` port. Policy model is **ReBAC**, with cross-principal contract tests (BOLA) per read endpoint.
- **Observability.** Structured JSON logs, distributed tracing, Prometheus metrics on every handler. Trace context is the source of truth for `correlation_id`.
- **Migrations.** Forward-only. A rollback is a new compensating migration. CI verifies hash-sum integrity and runs a safety scan on net-new migrations.
