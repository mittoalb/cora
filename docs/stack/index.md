# Stack

*Picks, reasons, swap triggers.*

Roles in [Architecture](../architecture/index.md). Pinned versions in `pyproject.toml`, `docker-compose.yml`, `Makefile`. Picks are starting points: seam discipline (ports + adapters, BC isolation) lets any one swap without touching the core.

## Pages

- [Backend](backend.md): language, HTTP, async DB, agent SDK, validation, settings, IDs, server.
- [Frontend](frontend.md): framework, lint, format.
- [Data](data.md): relational store, event store, vector index, migrations.
- [Auth](auth.md): authentication wiring, authorization model, policy language.
- [Observability](observability.md): logging, metrics, tracing, receivers.
- [Operations](operations.md): deployment, tooling.
- [Deferred](deferred.md): picks held until a real consumer demands them.
