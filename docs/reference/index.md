# Reference

*The internal contract the code follows.*

Not a tutorial. Not onboarding. The rules a human or LLM agent has to honor when modifying CORA so the codebase doesn't drift. If the code disagrees with this page, the code is wrong. For collaboration on the design (not the code), see [Contributing](../../CONTRIBUTING.md).

## Pages

- [Workflow](workflow.md): reading order, commits, branch flow, migrations, tests.
- [Layout](layout.md): BC structure, imports, naming, bootstrap, shared code.
- [Modeling](modeling.md): event sourcing, value objects, field grouping.
- [Patterns](patterns.md): read side, query slices, projections, idempotency, cross-aggregate validation.
- [Runtime](runtime.md): production hardening, logging, HTTP errors.
