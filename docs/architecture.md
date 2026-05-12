# Architecture

This document is the **layer-2** view of CORA: the patterns and roles the runtime is built from, with no product names. It answers "what does each piece do" rather than "which product implements it."

For the current concrete picks (which HTTP framework, which database, which migration tool) and the reasoning behind each, see [stack.md](stack.md). For working vocabulary, see [glossary.md](glossary.md). For onboarding and code conventions, see [CONTRIBUTING.md](contributing.md).

## Layered docs

| Layer | Vocabulary | Where it lives |
| --- | --- | --- |
| 1. Capability | What CORA does for users | [README.md](index.md) intro, project_overview |
| 2. Architecture | Roles and patterns, no products | this file |
| 3. Implementation | Current product picks and reasoning | [stack.md](stack.md), [CONTRIBUTING.md](contributing.md) |
| 4. Pinned versions | Exact strings | `apps/api/pyproject.toml`, `Makefile`, `infra/atlas/migrations/` |

A reader can stop at the layer they care about. A tech swap (HTTP framework, database, agent-protocol SDK) only ripples through layers 3 and 4.

## Domain modelling

CORA is structured as a set of **bounded contexts** (BCs). Each BC owns its own domain model, language, and API surface. Within a BC the unit of consistency is an **aggregate**, and the unit of behaviour is a **vertical slice**: one folder per command or query. Slices follow Functional Core / Imperative Shell:

- **Pure core.** Decider (`(state, command) -> events`) and evolver (`(state, event) -> state`) are pure functions. No I/O, no clock, no randomness.
- **Imperative shell.** The handler does I/O. All side effects (clock, ID generation, event store, authorisation, idempotency) enter the core through injected **ports** (Python `Protocol`s). Adapters implement the ports for production; tests substitute fakes.

Eight BCs are scaffolded so far. Their names and roles are listed in [glossary.md](glossary.md).

## State and history

CORA is **event-sourced**. Every state change produces one or more immutable events; aggregate state is reconstructed by folding the event stream. The event store has two enforced invariants:

- **Append-only at the database role level.** The application role has SELECT and INSERT on the events table; UPDATE, DELETE, and TRUNCATE are revoked. Migrations run under a separate admin role. Immutability is a database guarantee, not a convention.
- **Total order via a transaction-id cursor.** Every event carries the database transaction id, letting projection workers advance a bookmark without skipping in-flight inserts.

Read models come in two shapes:

- **Fold-on-read** for single-aggregate `GET` endpoints. Replays the stream on every read. O(events-per-stream).
- **Projection workers** for list, filter, and search endpoints. Background processes tail the events stream, advance a per-projection bookmark, and maintain denormalised tables. The projection-worker framework is generic; per-projection logic plugs in via a registry.

## API surfaces

Every command is exposed on two equivalent surfaces backed by the same handler:

- **REST.** HTTP for human and machine clients. OpenAPI-described.
- **Agent protocol.** For LLM-driven agents and tool-using clients. Same handler, different transport and schema convention.

The handler is the unit of authoritative behaviour; both surfaces are thin adapters around it. Adding a third surface (an agent-to-agent protocol, gRPC, etc.) means writing a third adapter; the domain core does not move.

## Cross-cutting concerns

- **Idempotency.** Create-style commands accept an `Idempotency-Key` header (per IETF draft). The store remembers `(key, command_name, body_hash) → result` and replays the cached result on retry.
- **Authentication.** The application trusts an `X-Principal-Id` header set by an upstream verifying proxy. Production deployments must front the API with a proxy that authenticates the caller, strips client-supplied principal headers, and sets the verified principal id.
- **Authorisation.** Every command and query passes through an `Authorize` port. The production policy model is **relationship-based access control (ReBAC)**, with cross-principal contract tests (BOLA coverage) per read endpoint.
- **Observability.** Structured JSON logs, distributed tracing, and Prometheus metrics on every handler. Trace context is the source of truth for `correlation_id`; routes and agent-protocol tools both derive it from the active span.
- **Schema migrations.** Forward-only. A rollback is a new migration that compensates, never a backward edit. CI verifies hash-sum integrity and runs a safety scan on net-new migrations.

## Modelling lenses

CORA's domain model borrows vocabulary and structure from established standards. These lenses give shared vocabulary with the broader operations and provenance communities; they do not constrain the implementation.

- **ISA-95** for the asset hierarchy (Enterprise / Site / Area / Unit / Assembly / Device).
- **ISA-88** for episodic procedures (the recipe ladder: Method, Practice, Plan, Run).
- **ISA-106** for continuous operations.
- **ISA-99 / IEC 62443** for trust topology (Zones, Conduits, Policies).
- **ISO/IEC 42001 + NIST AI RMF** for AI governance, surfaced in the Decision and Strategy BCs.
- **W3C PROV-O** for provenance vocabulary at API boundaries (Activity, Entity, Agent, used, wasGeneratedBy).
- **PIDINST + ISO 23527 (RAiD)** for persistent identifiers on instruments and research activities.

## Recipe ladder

The recipe ladder (Method, Practice, Plan, Run) is the mechanism that keeps CORA facility-neutral. A Method is a reusable procedure template. A Practice binds a Method to a site or capability set. A Plan binds a Practice to specific assets and a window. A Run executes a Plan and has a lifecycle FSM (started, held, resumed, stopped, completed, aborted, truncated). Site-specific behaviour lives at the Practice and Plan layers; Methods stay portable.

## Where this lives in code

- BCs: `apps/api/src/cora/<bc>/`
- Aggregates: `apps/api/src/cora/<bc>/aggregates/<aggregate>/`
- Vertical slices: `apps/api/src/cora/<bc>/features/<verb>_<aggregate>/`
- Ports: `apps/api/src/cora/infrastructure/ports/`
- Shared kernel: `apps/api/src/cora/infrastructure/kernel.py`
- Architecture-fitness tests: `apps/api/tests/architecture/`
