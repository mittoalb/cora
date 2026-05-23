# Modules

Each module is a bounded area of CORA's domain with its own aggregates, events, and slices. Every module page follows the same shape: purpose, maturity, aggregates, value objects, FSM, events, slices, storage, cross-module boundaries, and runnable examples.

<div class="cora-aside" markdown>

- **Two surfaces, same behavior.** Every slice exposes a **REST** path for human operators and integration callers (hit it with `curl`, `httpx`, `HTTPie`, or any HTTP client) and an **MCP** tool for agent callers via the Model Context Protocol SDK. The MCP tool name matches the slice verb, and the argument keys mirror the REST JSON body 1-to-1. Same payload, same errors, same events: pick whichever fits the caller.
- **Auth.** Every call carries the calling actor's identity. In bearer mode (`IDENTITY_PROVIDERS` configured) the same `BearerAuthMiddleware` verifies tokens for both REST and MCP streamable-HTTP, with audience bound per Surface; in legacy mode an `X-Principal-Id: <uuid>` header from a verifying proxy carries it instead. Either way, REST and MCP land on the same `principal_id` at the handler. See the [Auth page](../../stack/auth.md).
- **Idempotency.** Slices marked *required* in the Idempotency column of each module's Slices table accept an `Idempotency-Key: <uuid>` header. Resending the same key with the same body returns the cached response, so operator retries after network blips are safe.

</div>

## Pages

<div class="grid cards" markdown>

-   :material-play-circle-outline:{ .lg .middle } __Run__ <span class="md-maturity md-maturity--stable">stable</span>

    ---

    Execution layer of the recipe ladder. One Run is one execution instance with a closed FSM, parameter resolution, reading logbook, and cross-module anchors to Plan, Subject, Asset, Clearance, Campaign, and Calibration.

    [Read →](run/index.md)

-   :material-shield-check-outline:{ .lg .middle } __Safety__ <span class="md-maturity md-maturity--stable">stable</span>

    ---

    Formal regulatory clearances that gate work. ESAF, SAF, A-form, DUO, ESRA, ERA, PLHD, DOOR, BTR, and Form 9 lifecycles, with multi-step review chains and cross-module coverage queries.

    [Read →](safety/index.md)

-   :material-alert-circle-outline:{ .lg .middle } __Caution__ <span class="md-maturity md-maturity--stable">stable</span>

    ---

    Operator-authored tribal-knowledge notes. Lightweight three-state lifecycle, supersession-as-edit, non-blocking banners at Run.start. Distinct from Safety: never gates work, no review board.

    [Read →](caution/index.md)

-   :material-target-variant:{ .lg .middle } __Calibration__ <span class="md-maturity md-maturity--stable">stable</span>

    ---

    Empirical instrument values keyed by `(asset, quantity, operating_point)`. Append-only revisions, per-revision status, polymorphic source (Measured / Computed / Asserted), AsShot pinning into Run and Dataset.

    [Read →](calibration/index.md)

-   :material-robot-outline:{ .lg .middle } __Agent__ <span class="md-maturity md-maturity--stable">stable</span>

    ---

    Typed configuration for AI agents (RunDebriefer, CautionDrafter). Four-state lifecycle with Suspended pause, shared id with Access Actor, MCP tool allowlist, declarative budgets, and two cross-BC action slices.

    [Read →](agent/index.md)

-   :material-folder-multiple-outline:{ .lg .middle } __Campaign__ <span class="md-maturity md-maturity--stable">stable</span>

    ---

    Operator-declared coordinated study container above Run. Series, sweep, coordinated, or scheduling-block intent, five-state lifecycle with operator hold, atomic two-stream membership writes, and an open-status-default list view.

    [Read →](campaign/index.md)

-   :material-cog-play-outline:{ .lg .middle } __Operation__ <span class="md-maturity md-maturity--stable">stable</span>

    ---

    Episodic operational tasks: bakeout, calibration sweep, alignment, recovery. Five-state Procedure FSM with truncate for retroactive cleanup, polymorphic per-step entries (setpoint, action, check), and optional binding as a Phase-of-Run.

    [Read →](operation/index.md)

-   :material-water-pump:{ .lg .middle } __Supply__ <span class="md-maturity md-maturity--stable">stable</span>

    ---

    Continuously-available resources (photon beam, LN2, compressed air, electrical power, vacuum). Five-state availability FSM with Phoebus-style latched recovery, typed `(scope, kind, name)` address, and operator-asserted transitions today.

    [Read →](supply/index.md)

-   :material-account-key-outline:{ .lg .middle } __Access__ <span class="md-maturity md-maturity--stable">stable</span>

    ---

    Foundation BC for principal identity: one aggregate (`Actor`), two events, two-state lifecycle, shared identity with `Agent`. The "who you are" layer that every other module references when attributing an event.

    [Read →](access/index.md)

-   :material-wrench-outline:{ .lg .middle } __Equipment__ <span class="md-maturity md-maturity--stable">stable</span>

    ---

    Two aggregates (`Family`, `Asset`), six-level hierarchy, four-state lifecycle, three-state condition orthogonal to lifecycle, settings-schema validation against the Family-declared Capability, and typed ports for wiring devices into Plans.

    [Read →](equipment/index.md)

-   :material-book-open-page-variant-outline:{ .lg .middle } __Recipe__ <span class="md-maturity md-maturity--stable">stable</span>

    ---

    Four aggregates forming the abstract-to-bound ladder: `Capability`, `Method`, `Practice`, `Plan`. ISA-88 General/Site/Master/Control recipe progression; the "what we plan to do" layer above Run.

    [Read →](recipe/index.md)

-   :material-shield-lock-outline:{ .lg .middle } __Trust__ <span class="md-maturity md-maturity--stable">stable</span>

    ---

    ISA-99/IEC-62443 topology of `Zone`, `Conduit`, `Surface`, `Policy`. Pure Policy Decision Point; Authorize port gates every write-side decider in CORA; first concrete entries-table observation logbook for per-decision audit.

    [Read →](trust/index.md)

-   :material-cube-outline:{ .lg .middle } __Subject__ <span class="md-maturity md-maturity--stable">stable</span>

    ---

    One aggregate, seven-state lifecycle with three terminal dispositions, mount/dismount cycle, Asset-lifecycle guard on mount, generic across science domains (materials samples, biological specimens, manufactured parts, astronomical targets, computational subjects).

    [Read →](subject/index.md)

-   :material-database-outline:{ .lg .middle } __Data__ <span class="md-maturity md-maturity--stable">stable</span>

    ---

    One aggregate (`Dataset`), two-state lifecycle plus orthogonal three-state Intent axis (`Trial`, `Production`, `Retracted`), lineage edges with existence and status guards, immutable AsShot calibration citation set.

    [Read →](data/index.md)

-   :material-scale-balance:{ .lg .middle } __Decision__ <span class="md-maturity md-maturity--stable">stable</span>

    ---

    One aggregate, atomic-immutable for decision facts, `parent_id` chains for corrections, appeals, supersessions, and invalidations. PROV-AGENT-aligned field names, ISO 17025 `decision_rule` citation, operator rating accrual channel.

    [Read →](decision/index.md)

</div>
