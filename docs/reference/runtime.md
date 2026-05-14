# Runtime

*Production hardening, logging, HTTP errors.*

## Production hardening

Wired in `cora/api/main.py:create_app()`.

- **Body size limit.** `BodySizeLimitMiddleware` returns 413 over `Settings.max_request_body_size_bytes` (default 1 MiB). Production also enforces at the reverse proxy.
- **Prometheus `/metrics`.** Per-app `CollectorRegistry` (global crashes on a second `TestClient(create_app())`). Hidden from its own counters and from OpenAPI.
- **OpenTelemetry tracing.** `Settings.otel_exporter`: `none`/`console`/`otlp`. OTLP honours `OTEL_EXPORTER_OTLP_*` env vars. Trace context is the source of truth for correlation: `current_correlation_id()` returns `UUID(int=trace_id)`. Handler spans via `with_tracing` in `wire.py`; name `<bc>.<command|query>.<command_name>`.
- **Auth (`X-Principal-Id`).** `get_principal_id` trusts the header. Absent: `Settings.require_authenticated_principal` controls fallback (False = `SYSTEM_PRINCIPAL_ID`; True = 401). **Production MUST front with an auth proxy** that verifies credentials, strips client-supplied headers, and sets the verified UUID.
- **Production startup gate.** Refuses to boot if `app_env in {"prod","production"}` AND `require_authenticated_principal=False`. Opt in: `APP_ENV=prod`, `REQUIRE_AUTHENTICATED_PRINCIPAL=true`, `DATABASE_URL=postgresql://cora_app:.../cora`.
- **DB role separation.** `cora_app` has SELECT + INSERT on `events` + `entries_*`; UPDATE/DELETE/TRUNCATE revoked. Migrations run as the database owner. `proj_*` tables get full DML.

## Logging

Two patterns:

- **Handlers**: `<verb>.<event>` (`register_actor.start`, `register_actor.denied`, `register_actor.success`). Every handler emits `start` plus `denied` or `success`. Decider failures propagate as exceptions.
- **Cross-cutting**: `<concern>.<event>` (`idempotency.cache_hit`, `body_size_limit.rejected`).

**Field names:**

- `correlation_id`: request correlation (str-cast UUID)
- `causation_id`: command handlers only; upstream event id (`null` for HTTP/MCP root). Always emitted.
- `principal_id`: calling principal (str-cast UUID)
- `command_name` / `query_name`: dataclass name
- `actor_id` (or `<aggregate>_id`): aggregate id when in scope. One key per concept.

## HTTP errors

- **In routes**: `raise HTTPException(...)`. FastAPI idiom.
- **In exception handlers**: `return JSONResponse(...)`. Raising `HTTPException` inside a handler creates nested-exception pitfalls ([FastAPI guidance](https://fastapi.tiangolo.com/tutorial/handling-errors/)).

Routes raise; handlers return. Same JSON shape over the wire.
