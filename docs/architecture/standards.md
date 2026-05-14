# Standards

*ISA lenses, recipe ladder, in-code map.*

Shared vocabulary with the field, not a constraint on implementation. CORA borrows ISA names (Asset, Recipe, Zone) and PROV-O semantics so a facility engineer recognises the model on first contact. The standards lend the shape; the implementation stays CORA's.

## Lenses

| Standard | Provides | Lands in |
| --- | --- | --- |
| ISA-95 | asset hierarchy (Enterprise / Site / Area / Unit / Assembly / Device) | `equipment` |
| ISA-88 | episodic procedures (recipe ladder: Method / Practice / Plan / Run) | `recipe`, `run` |
| ISA-106 | continuous operations | `operation`, `supply` (planned) |
| ISA-99 / IEC 62443 | trust topology (Zones, Conduits, Policies) | `trust` |
| ISO/IEC 42001 + NIST AI RMF | AI governance frameworks | `decision`, `strategy` (planned) |
| W3C PROV-O | provenance vocabulary (Activity, Entity, Agent, used, wasGeneratedBy) | outbound API payloads |
| RAiD (ISO 23527) | research activity identifier | `RunStarted` (forward-compat field) |

PROV-O is treated as frozen 2013 bedrock vocabulary; the W3C Provenance Working Group is closed and the spec is not moving.

Asset persistent identifiers (PIDINST profile vs raw DataCite Instrument resourceType vs other) are a deferred pick; see [Deferred](../stack/deferred.md). CORA reserves the capacity for publication-quality persistent IDs on `equipment` Assets and decides the minting profile when the first Asset needs to be cited externally.

## Recipe ladder

Method, Practice, Plan, Run. A Method is a reusable template. A Practice binds it to a site. A Plan binds a Practice to specific assets and a window. A Run executes a Plan with a lifecycle FSM. Site-specific behaviour lives at Practice and Plan; Methods stay portable.

## In code

For where each lens lands in the repo (BCs, aggregates, slices, ports, kernel, fitness tests), see [Reference/Layout](../reference/layout.md).
