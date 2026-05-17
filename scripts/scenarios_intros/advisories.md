Agent-driven subscriber output. Each scenario here exercises a CORA AI agent that observes domain events as a subscriber and emits an advisory `DecisionRegistered`. Today's three scenarios cover `RunDebrief` on terminal Run events (Nominal, Degraded, Aborted outcomes); the next sibling (`CautionDrafter`) lands here when its Stage 2 scenarios ship.

Advisory means non-binding: the Decision is operator-overrideable, the rating system (`DecisionRated`) closes the feedback loop, and an `agent:RunDebrief:v1` decision rule is captured for downstream calibration. None of these scenarios block a Run from starting or completing.

This cluster scales with the Agent BC roadmap: every new agent kind adds one scenario per outcome it differentiates.
