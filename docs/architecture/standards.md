# Standards

*ISA lenses, recipe ladder, in-code map.*

Shared vocabulary with the field, not a constraint on implementation.

## Lenses

| Standard | Provides | Lands in |
| --- | --- | --- |
| ISA-95 | Asset hierarchy: Enterprise / Site / Area / Unit / Assembly / Device | `equipment` |
| ISA-88 | Episodic procedures (recipe ladder: Method / Practice / Plan / Run) | `recipe`, `run` |
| ISA-106 | Continuous operations | (Track B, future) |
| ISA-99 / IEC 62443 | Trust topology: Zones, Conduits, Policies | `trust` |
| ISO/IEC 42001 + NIST AI RMF | AI governance | `decision`, `strategy` (planned) |
| W3C PROV-O | Provenance vocabulary (Activity, Entity, Agent, used, wasGeneratedBy). W3C WG closed; treat as frozen 2013 bedrock vocabulary, not a moving spec. | API boundaries |
| RAiD (ISO 23527) | Research Activity Identifier | `RunStarted` (forward-compat field) |

Asset persistent identifiers (PIDINST profile vs raw DataCite Instrument resourceType vs other) are a deferred pick: see [Deferred](../stack/deferred.md). PIDINST adoption is thin (HZB at BESSY II is the only confirmed photon-science adopter as of 2026); CORA reserves the *capacity* for publication-quality persistent IDs on `equipment` Assets and decides the minting profile when the first Asset needs to be cited externally.

## Recipe ladder

Method, Practice, Plan, Run. A Method is a reusable template. A Practice binds it to a site. A Plan binds a Practice to specific assets and a window. A Run executes a Plan with a lifecycle FSM (started, held, resumed, stopped, completed, aborted, truncated). Site-specific behaviour lives at Practice and Plan; Methods stay portable.

## In code

- BCs: `apps/api/src/cora/<bc>/`
- Aggregates: `<bc>/aggregates/<name>/`
- Slices: `<bc>/features/<verb>_<aggregate>/`
- Ports: `apps/api/src/cora/infrastructure/ports/`
- Kernel: `apps/api/src/cora/infrastructure/kernel.py`
- Fitness tests: `apps/api/tests/architecture/`
