# Architecture

*Roles, not products. Patterns, not picks.*

Most architecture docs name vendors and rot the moment one is replaced. CORA's doesn't. Each role is described by what it does in the system. The product that fills the role today lives one layer down in [Stack](../stack/index.md), so a swap is a stack change, not an architecture change.

## Pages

- [Model](model.md): bounded contexts, aggregates, vertical slices, FCIS.
- [State](state.md): event sourcing, projections, read models.
- [Surfaces](surfaces.md): surface adapters, handlers, cross-cutting concerns.
- [Standards](standards.md): ISA lenses, recipe ladder, in-code map.
