# Glossary

For anyone reading CORA. Each term defined once and used the same way in code, commits, and prose. Names are load-bearing; drift in vocabulary is drift in the model. If a page uses a term differently, the page is wrong.

## Architecture

*BCs, aggregates, deciders, slices, FCIS, ports, kernel.*

- **Bounded context (BC).** A self-contained slice of the domain with its own model, language, API surface. Examples: `access`, `equipment`, `recipe`, `run`, `data`, `decision`, `subject`, `trust`.
- **Aggregate.** Consistency boundary inside a BC. Holds state, validates commands, emits events.
- **Decider.** Pure `(state, command) -> events`. Business rules. No I/O.
- **Evolver.** Pure `(state, event) -> state`. Folds events into state.
- **Fold-on-read.** Rebuild aggregate state by replaying events on every command. No snapshots yet.
- **Vertical slice.** One folder per command or query: `command.py`, `decider.py`, `handler.py`, `route.py`, `tool.py`.
- **FCIS.** Functional core / imperative shell. Pure deciders and evolvers; all I/O at the shell via injected ports.
- **Port.** A `Protocol` defining a side-effect seam (clock, ID generator, event store, authorize, idempotency).
- **Kernel.** Shared kernel: cross-BC primitives (event envelope, deps wiring, authorize factory).
- **Slim vs Lifecycle aggregate.** Two patterns for cheap replay. Slim closes out and starts fresh; Lifecycle carries state across phases.

## Events

*Event store, streams, positions, transactions, projections.*

- **Event store.** Append-only Postgres table of immutable events. INSERT-only at the DB role level.
- **Stream.** All events for one aggregate instance, ordered by version.
- **Position.** Global monotonic ordinal of an event in the store.
- **transaction_id (xid8).** PG18 transaction identifier on every event. Lets projection workers advance a cursor without skipping in-flight inserts.
- **Projection.** A read model built by replaying events into a denormalized table. Workers tail the store and advance a bookmark.

## Surfaces

*REST, MCP, A2A.*

- **REST.** FastAPI HTTP endpoints under `/<resource>`. OpenAPI at `/docs`.
- **MCP.** Model Context Protocol, the LLM-agent surface. Streamable HTTP at `/mcp`. Same handler as REST.
- **A2A.** Agent-to-Agent protocol. Planned trust-boundary surface for cross-organization agent calls (deferred).

## Standards

*ISA, ISO/IEC, NIST, PROV-O, RAiD.*

- **ISA-95.** Manufacturing operations hierarchy: Enterprise / Site / Area / Unit / Assembly / Device. Used for the Asset model.
- **ISA-88.** Batch control. Basis for Track A (Method / Practice / Plan / Run).
- **ISA-106.** Continuous-process operations. Basis for Track B.
- **ISA-99 / IEC 62443.** Industrial cybersecurity. Basis for Track C: Zones, Conduits, Policies (`trust` BC).
- **ISO/IEC 42001 + NIST AI RMF.** AI governance frameworks. Inform Decision and Strategy BCs.
- **W3C PROV-O.** Provenance ontology. Borrowed at API boundaries (Activity, Entity, Agent, used, wasGeneratedBy). W3C Provenance Working Group is closed; PROV-O is frozen 2013 bedrock vocabulary, not a moving spec. Community momentum lives in downstream consumers (RO-Crate, FAIRSCAPE).
- **RAiD (ISO 23527).** Research Activity Identifier. Forward-compat field on `RunStarted`.

Watch-only (not adopted as a glossary term, see [Deferred](../stack/deferred.md)):

- **PIDINST.** RDA-WG recommendation for persistent IDs of physical instruments, layered on DataCite Schema 4.5+ via `resourceTypeGeneral=Instrument`. Adoption is thin (HZB at BESSY II is the only confirmed photon-science adopter as of 2026), so CORA treats it as a watch item rather than a standard. The Asset model reserves capacity for a publication-quality persistent ID; the minting profile (PIDINST vs raw DataCite Instrument resourceType vs other) is decided when first needed.

## Authz

*ReBAC, BOLA, Cedar, principal, actor vs profile.*

- **ReBAC.** Relationship-based access control (planned: SpiceDB or OpenFGA). For multi-stakeholder ownership common in shared facilities.
- **BOLA.** Broken Object-Level Authorization (OWASP API #1). Covered by a parametrized cross-principal contract test on every read endpoint.
- **Cedar.** Policy language used in `decision` BC predicates.
- **Principal.** Authenticated identity attached to every command and event envelope. Required in production via `REQUIRE_AUTHENTICATED_PRINCIPAL=true`.
- **Actor vs Profile.** `Actor` is the immutable identity in events; `Profile` is the mutable PII row, separately stored and erasable. GDPR-shaped.

## Equipment

*Assets, Families, Affordances. The device-classification side of Equipment BC.*

- **Asset.** A physical equipment instance registered in the hierarchy (Enterprise / Site / Area / Unit / Device per ISA-95). Belongs to one or more Families.
- **Family.** A device-class abstraction: WHAT kind of equipment this is, device-agnostic. Examples: `RotaryStage`, `LinearStage`, `Camera`, `Scintillator`, `Hexapod`, `Mirror`. Until phase 5i this aggregate was named `Capability`; phase 6k (shipped 2026-05-18) introduced a NEW Recipe BC `Capability` aggregate at the operations-layer (separate concept; see below).
- **Affordance.** A closed-enum primitive a Family declares it supports. Three patterns: action affordances (`-able` suffix, "device supports doing X"; 24 items), signal affordances (noun, "device exposes signal X"; 3 items), lifecycle affordances (noun, "device has lifecycle property X"; 1 item). Cross-BC contract: at `define_plan` time, the union of every wired Asset's Families' affordances must cover the bound Method's Capability `required_affordances` (otherwise `PlanAffordancesNotSatisfiedError`, 409). See [Affordances reference](affordances.md) for the 28-item v1 list.

## Recipe ladder

*Capability, method, practice, plan, run, logbook.*

- **Capability.** *(Recipe BC, phase 6k)* An operations-layer template declaring WHAT a Method or Procedure can do: `required_affordances` (the Family-affordance contract any binding must cover), `parameter_schema` (the parameter contract Method.parameters_schema must be a subset of), `executor_shapes` (closed v1 enum `{METHOD, PROCEDURE}` — which executor kinds may bind). Distinct from Equipment Family (`what a device IS`); Capability is `what an operation provides`. Methods bind via `Method.capability_id` (REQUIRED post-6l-strict); Procedures bind via `Procedure.capability_id` (optional). Namespaced `cora.capability.*` codes; status FSM `Defined → Versioned → Deprecated` with optional `replaced_by_capability_id` (LOINC `MAP_TO` precedent).
- **ExecutorShape.** *(Recipe BC, phase 6k closed v1 StrEnum)* Declares which executor kinds may implement a Capability: `METHOD` (heavyweight science executor producing datasets via Plan → Run) or `PROCEDURE` (lightweight ceremony executor without datasets, ISA-106 atoms). One Capability may declare both shapes.
- **Method.** A reusable technique template. Binds to one Capability via `capability_id` (REQUIRED) and to a set of Equipment Families via `needed_families` (hardware-compat). Method's `parameters_schema` must be a structural subset of the bound Capability's `parameter_schema` (`MethodParametersNotSubsetError`, 409).
- **Practice.** A Method bound to a site or set of Families.
- **Plan.** A Practice bound to specific Assets and a window.
- **Run.** An execution of a Plan. FSM: started, held, resumed, stopped, completed, aborted, truncated.
- **Logbook.** Append-only narrative log on a Run or Decision. Used for OTel `gen_ai.*` reasoning entries on Decisions.
