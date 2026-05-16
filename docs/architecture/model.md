# Model

*Bounded contexts, aggregates, vertical slices.*

The shape under every CORA feature: a BC owns a slice of the domain, an aggregate owns a consistency boundary inside it, a vertical slice owns one command or query end-to-end. Get these three right and adding a feature stops being a refactor.

## Bounded contexts

CORA is a set of bounded contexts (BCs). Each owns its model, language, and API surface.

| BC | Owns | Status |
| --- | --- | --- |
| `access` | Actors with identity and authentication | Active |
| `subject` | Subjects under measurement, custody, and hazard | Active |
| `equipment` | Capabilities and Asset hierarchy | Active |
| `recipe` | Methods, Practices, and Plans (the recipe ladder) | Active |
| `run` | Run executions with lifecycle FSM and audit | Active |
| `decision` | Decisions and provenance for consequential choices | Active |
| `data` | Datasets and transfers (lineage, tiers) | Active |
| `trust` | Zones, Conduits, and Policies | Active |
| `supply` | Continuous resources (beam, power, cooling, LN2) | Active |
| `operation` | Episodic procedures (bakeout, calibration) | Active |
| `safety` | Clearances, hazard classifications, approval chains | Active |
| `caution` | Operator tribal-knowledge cautions (workarounds, quirks) | Active |
| `campaign` | Multi-Run studies (in-situ, operando, screening) | Active |
| `strategy` | Decision-making policies (mode, thresholds, fallbacks) | Planned |
| `budget` | Resource allocation (limits, circuit breakers) | Planned |

## Aggregates

The unit of consistency inside a BC: state, invariants, events.

## Vertical slices

One folder per command or query, holding everything the slice needs:

```
features/<verb>_<aggregate>/
├── command         input shape
├── decider         pure rule: (state, command) -> events
├── handler         shell: wires core to ports
└── adapters        one per surface (HTTP API, agent tool, ...)
```

Independently readable, testable, deletable. For the in-repo file layout, see [Reference/Layout](../reference/layout.md).

<div class="cora-aside" markdown>

What each piece does
{: .cora-kicker }

- **Command.** Immutable input shape, one per slice. Captures the caller's intent. Structurally validated at the adapter, semantically validated by the decider.
- **Functional core.** Decider takes a command and current state, returns events. Evolver folds events back into state. Both pure, no I/O.
- **Imperative shell.** Handler wires the core to side-effect ports (clock, IDs, event store, authorize, idempotency). Real ports in production, fakes in tests.
- **Thin adapters.** One per surface, translates protocol-specific input into the same handler call. Schema validation only, no business rules.

</div>

Query slices follow the same shape with `query` in place of `command` and no decider, since there's no state change. Single-record reads fold the stream; list and filter reads hit a projection. See [Reference/Patterns](../reference/patterns.md).
