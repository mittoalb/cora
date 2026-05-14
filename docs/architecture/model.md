# Model

*Bounded contexts, aggregates, vertical slices.*

## Bounded contexts

CORA is a set of bounded contexts (BCs). Each owns its model, language, and API surface.

| BC | Owns | Status |
| --- | --- | --- |
| `access` | Identity and authentication (Actors) | Active |
| `subject` | Subjects under measurement, custody, hazard | Active |
| `equipment` | Capabilities and Asset hierarchy | Active |
| `recipe` | Methods, Practices, Plans (the recipe ladder) | Active |
| `run` | Run executions with FSM and audit | Active |
| `decision` | Audit and provenance for consequential choices | Active |
| `data` | Datasets and transfers (lineage, tiers) | Active |
| `trust` | Zones, Conduits, Policies (ISA-99 / IEC 62443) | Active |
| `campaign` | Multi-Run studies (in-situ, operando, screening) | Planned |
| `supply` | Continuous resources (beam, power, cooling, LN2) | Planned |
| `operation` | Episodic 106-procedures (bakeout, calibration) | Planned |
| `strategy` | Decision-making policies (mode, thresholds, fallbacks) | Planned |
| `budget` | Resource allocation with limits and circuit breakers | Planned |

## Aggregates

The unit of consistency inside a BC: state, invariants, events.

## Vertical slices

One folder per command or query, holding everything the slice needs:

```
features/register_actor/
├── command.py    input shape
├── decider.py    pure rule: (state, command) -> events
├── handler.py    shell: wires core to ports
├── route.py      REST adapter
└── tool.py       MCP adapter
```

Independently readable, testable, deletable.

- **Functional core.** Decider `(state, command) -> events` decides which facts a command should emit. Evolver `(state, event) -> state` folds each fact back into state. Both pure, no I/O.
- **Imperative shell.** Handler injects the side-effect ports (clock, IDs, event store, authorize, idempotency), each typed as a `Protocol`. Real adapters in production, fakes in tests.
- **Thin adapters.** `route.py` (REST) and `tool.py` (MCP) translate protocol-specific input (HTTP body, MCP arguments) into the same handler call. Schema validation only, no business rules. New surface, new adapter; the core does not move.
