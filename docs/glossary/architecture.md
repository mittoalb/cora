# Architecture terms

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
