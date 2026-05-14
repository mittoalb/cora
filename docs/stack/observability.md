# Observability

*Logging, metrics, tracing, receivers.*

## Emitters

| Role | Pick | Why | Swap trigger |
| --- | --- | --- | --- |
| Structured logging | structlog | JSON logs, processor pipeline for trace-context injection | Stays |
| Metrics | prometheus-client + prometheus-fastapi-instrumentator | Industry-standard scrape; per-app `CollectorRegistry` survives repeated `TestClient` | Push metrics (OTLP-only) |
| Tracing | OpenTelemetry (api/sdk + asyncpg + fastapi) | Vendor-neutral; `gen_ai.*` semconv for Decision-BC reasoning logbooks | Stays |
| Tracing transport | OTLP over HTTP | Vendor-neutral; `OTEL_EXPORTER_OTLP_*` env vars passed through | gRPC variant if a backend requires it |

## Receivers

All three production receivers are deferred (no production deployment is live). Named so the gap is visible.

| Role | Status | Trigger |
| --- | --- | --- |
| Log aggregator | Deferred (Loki, ELK, Datadog) | First non-local deployment |
| Metrics scraper | Deferred (Prometheus server, Mimir) | First non-local deployment |
| Tracing backend | Deferred (Jaeger, Tempo, Honeycomb) | First non-local deployment |
| OTel Collector | Deferred (in-process vs sidecar) | First non-local deployment, or >1 signal type needs preprocessing |
