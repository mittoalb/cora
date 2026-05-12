# Glossary

Terse definitions for the vocabulary that shows up in CORA code, commits, and design notes. Linked from the [README](../README.md) and [CONTRIBUTING.md](../CONTRIBUTING.md).

## DDD and architecture

- **Bounded context (BC).** A self-contained slice of the domain with its own model, language, and API surface. CORA has 8 scaffolded so far: `access`, `equipment`, `recipe`, `run`, `data`, `decision`, `subject`, `trust`. One folder per BC under [apps/api/src/cora/](../apps/api/src/cora/).
- **Aggregate.** The consistency boundary inside a BC. Holds state, decides whether a command is valid, emits events. Located under `<bc>/aggregates/<name>/`.
- **Decider.** A pure function `(state, command) -> events`. Contains the business rules. No I/O.
- **Evolver.** A pure function `(state, event) -> state`. Folds events into the current aggregate state.
- **Fold-on-read.** Rebuild aggregate state by replaying events from the store on every command. No persisted snapshots yet (see [project_deferred.md](../../.claude/projects/-Users-dgursoy-Documents-Github-cora/memory/project_deferred.md) for the trigger).
- **Vertical slice.** One folder per command or query containing `command.py`, `decider.py`, `handler.py`, `route.py`, `tool.py`. Found under `<bc>/features/<slice>/`.
- **Functional core, imperative shell (FCIS).** Pure functions in the core (decider, evolver), all side effects (DB, clock, IDs, HTTP) at the shell. Side effects enter via injected ports.
- **Port.** A `Protocol` defining a side-effect seam (clock, ID generator, event store, authorize, idempotency). Adapters implement them. See [infrastructure/ports/](../apps/api/src/cora/infrastructure/ports/).
- **Kernel.** CORA's Shared Kernel: the small set of cross-BC primitives (event envelope, deps wiring, authorize factory). See [infrastructure/kernel.py](../apps/api/src/cora/infrastructure/kernel.py).
- **Slim vs Lifecycle aggregate.** Two patterns for keeping replay cheap. Slim aggregates close out and start fresh; lifecycle aggregates carry state across phases. See `project_fold_cost_principles.md` in memory.

## Event sourcing

- **Event store.** Append-only Postgres table of immutable events. INSERT-only at the DB role level (REVOKE UPDATE/DELETE on the app role). See [infrastructure/postgres/event_store.py](../apps/api/src/cora/infrastructure/postgres/event_store.py).
- **Stream.** All events for one aggregate instance, ordered by version.
- **Position.** Global monotonic ordinal of an event in the store.
- **transaction_id (xid8).** PG18 transaction identifier on every event. Lets projection workers advance a cursor without missing in-flight inserts (Khyst + Dudycz pattern).
- **Projection.** A read model built by replaying events into a denormalized table. Workers tail the store and advance a bookmark.

## API surfaces

- **REST.** FastAPI HTTP endpoints under `/<resource>`. OpenAPI at `/docs`.
- **MCP.** Model Context Protocol, the LLM-agent surface. Streamable HTTP transport mounted at `/mcp`. Same handler as REST.
- **A2A.** Agent-to-Agent protocol. CORA's planned trust-boundary surface for cross-organization agent calls (deferred).

## Modeling lenses

- **ISA-95.** Structural backbone for manufacturing operations: Enterprise / Site / Area / Unit / Assembly / Device hierarchy. CORA uses it for the Asset model.
- **ISA-88.** Batch-control standard, the basis for CORA's Track A (episodic procedures: Method / Practice / Plan / Run).
- **ISA-106.** Continuous-process operations, the basis for CORA's Track B.
- **ISA-99 / IEC 62443.** Industrial cybersecurity. The basis for CORA's Track C: Zones, Conduits, Policies in the `trust` BC.
- **ISO/IEC 42001 + NIST AI RMF.** AI governance frameworks. Inform CORA's Decision and Strategy BCs.
- **W3C PROV-O.** Provenance ontology. CORA borrows its vocabulary at API boundaries (Activity, Entity, Agent, used, wasGeneratedBy).
- **PIDINST.** Persistent identifiers for instruments. CORA's Asset uses PIDINST DOIs for site-level equipment.
- **RAiD (ISO 23527).** Research Activity Identifier. Forward-compat field on `RunStarted`.

## Authorization

- **ReBAC.** Relationship-based access control (the planned model: SpiceDB or OpenFGA). Designed for multi-stakeholder ownership common in shared-facility settings.
- **BOLA.** Broken Object-Level Authorization (OWASP API #1). CORA has a parametrized cross-principal contract test that covers every read endpoint as it lands.
- **Cedar.** Policy language used in `decision` BC predicates such as `has_determining_policies`.
- **Principal.** The authenticated identity attached to every command and event envelope. Required in production via `REQUIRE_AUTHENTICATED_PRINCIPAL=true`.
- **Actor vs Profile.** `Actor` is the immutable identity carried in events; `Profile` is the mutable PII row, separately stored and erasable. GDPR-shaped.

## Recipe ladder

- **Method.** A reusable procedure template. The most abstract layer.
- **Practice.** A method bound to a site or capability set.
- **Plan.** A practice bound to specific assets and a window.
- **Run.** An execution of a plan. Has a lifecycle FSM (started, held, resumed, stopped, completed, aborted, truncated).
- **Logbook.** Append-only narrative log attached to a Run or Decision. Used for OTel `gen_ai.*` reasoning entries on Decisions, and for cached telemetry on Runs (planned).

## Tooling

- **uv.** Python package and venv manager. Replaces pip + virtualenv + pip-tools.
- **Atlas.** Schema migration tool. Migrations live in [infra/atlas/migrations/](../infra/atlas/migrations/), forward-only.
- **tach.** Python import-boundary linter. Enforces BC isolation.
- **Ruff.** Python linter and formatter.
- **Pyright.** Python type checker, run in strict mode.
- **Biome.** JS/TS linter and formatter (frontend, planned).
