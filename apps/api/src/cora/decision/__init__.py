"""Decision bounded context.

Owns the structured-audit story for every consequential choice in
CORA, human approval, AI inference, agent action, operator
override. Single aggregate (Decision), unified across deciders.

## Why "decisions" is its own BC

The trigger fired in Phase 6f: 4 free-form `reason` fields shipped
(RunAborted.reason, RunStopped.reason, RunTruncated.reason,
DiscardDataset.reason) and the BC-map prose specifically named that
threshold ("first non-trivial decision needing structured audit").
Free text is enough for the moment of the action; structured audit
is what the next regulator / AI-act audit / scientific-replicability
review will demand.

## Aggregate is atomic-immutable; chains carry corrections

Decisions are append-only. Corrections, exceptions, appeals, and
supersessions land as NEW Decisions with `parent_id` pointing at
the prior and `override_kind` explaining the transition.

**Latest-in-chain wins** is the canonical projection rule for
consumers walking a Decision's parent chain. The aggregate-read
returns one Decision (the one identified by id); chain navigation
is the consumer's job. When a projection materializes "current
state of decision X," it walks parent_id back-pointers in the
inverse direction (x.parent → child(parent==x)) to find the latest
override.

## Standards alignment (gate-review locks; 2026 survey + validation pass)

  - **PROV-AGENT (eScience 2025)**: field naming aligns with
    PROV-O agent / activity vocabulary at the boundary; in-domain
    stays on primitives.
  - **NIST AI RMF + ISO/IEC 42001 + EU AI Act Article 12**:
    INSERT-only Postgres + event sourcing satisfies the automatic
    immutable record-keeping mandate by construction.
  - **ISO 17025 Clause 7.1.3 + ILAC-G8:09/2019**: `decision_rule`
    + `decision_inputs` carry the rule-and-its-inputs that a lab
    accreditation auditor will demand for any conformance decision.
  - **OPA Decision Logs**: PolicyGrant context's payload is
    isomorphic to OPA's `{decision_id, input, result, timestamp,
    metrics}` shape. `alternatives` carries the determining policy
    IDs Cedar-style.
  - **Anthropic extended-thinking signature**: `reasoning_signature`
    field provides per-decision content-addressing for tamper-
    evidence beyond row-level INSERT-only.
  - **OpenTelemetry GenAI semconv (gen_ai.*)**: AI-decider Logbook
    entries (8c) emit `gen_ai.request.model`, `gen_ai.usage.*`,
    `gen_ai.tool.*` etc. Aligning at carrier-time costs nothing,
    retrofitting later is painful.


Single aggregate (Decision). Three slices planned:
  - `register_decision` (8a, create-style; idempotency-wrapped;
    cross-aggregate validation via DecisionRegistrationContext for
    Actor + optional parent Decision)
  - `get_decision` (8a, read side; fold-on-read)
  - confidence_band derived field + decision_rule registry doc +
    Cedar-style PolicyGrant convention (8b, light slice)
  - AI-decider Logbook integration with OpenTelemetry `gen_ai.*`
    attributes (8c)

## Deferred-with-trigger

  - Hard Run-BC reason migration (trigger: compliance audit
    demand or first structured-query consumer); planned path is
    additive `decision_id: UUID | None` on each terminal event,
    NOT replacement of `reason: str`.
  - OPA decision-log export endpoint (trigger: first OPA integration).
  - W3C VC 2.0 cross-org Decision export (trigger: first cross-org
    export request).
  - prEN 18229-1 / ISO/IEC DIS 24970 conformance (trigger: standard
    finalizes or first EU-AI-Act-Annex-III customer).

Layout (mirrors every other BC):
    aggregates/decision/      -- aggregate state, events, evolver, read
    features/<verb>_decision/ -- vertical slice
    wire.py                   -- DecisionHandlers bundle + wire_decision(deps)
    routes.py                 -- register_decision_routes(app)
    tools.py                  -- register_decision_tools(mcp, *, get_handlers)
"""

from cora.decision._projections import register_decision_projections
from cora.decision.errors import OverrideKindRequiresParentError, UnauthorizedError
from cora.decision.routes import register_decision_routes
from cora.decision.tools import register_decision_tools
from cora.decision.wire import DecisionHandlers, wire_decision

__all__ = [
    "DecisionHandlers",
    "OverrideKindRequiresParentError",
    "UnauthorizedError",
    "register_decision_projections",
    "register_decision_routes",
    "register_decision_tools",
    "wire_decision",
]
